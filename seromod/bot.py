from __future__ import annotations

import asyncio
import logging
import os
import sys

import discord

from seromod.agent.gemini_brain import GeminiBrain
from seromod.agent.runtime import AgentRuntime
from seromod.agent.task import AgentTask, TaskStatus
from seromod.config import config
from seromod.guild_handle import (
    CategoryInfo,
    ChannelInfo,
    ChannelType,
    GuildHandle,
    MemberInfo,
    MessageInfo,
    RoleInfo,
)
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.policy.engine import PolicyEngine
from seromod.skills.conversation import ConversationSkill
from seromod.skills.moderation import ModerationSkill
from seromod.skills.server_builder import ServerBuilderSkill
from seromod.tools.categories import CreateCategoryTool, GetCategoriesTool
from seromod.tools.channels import CreateChannelTool, DeleteChannelTool, GetChannelsTool
from seromod.tools.members import BanMemberTool, KickMemberTool, TimeoutMemberTool
from seromod.tools.memory_tools import SearchDecisionsTool
from seromod.tools.messages import SendMessageTool
from seromod.tools.registry import ToolRegistry
from seromod.tools.roles import CreateRoleTool, GetRolesTool
from seromod.tools.server import GetServerStateTool
from seromod.tools.workspace_memory import (
    MemoryReadTool,
    MemorySearchTool,
    MemoryUpdateTool,
    MemoryWriteTool,
)

log = logging.getLogger("seromod.bot")


class DiscordGuildWrapper(GuildHandle):
    """Production GuildHandle wrapping a live discord.Guild object."""

    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.guild_id = guild.id
        self.name = guild.name

    async def get_channels(self) -> list[ChannelInfo]:
        results: list[ChannelInfo] = []
        for ch in self.guild.channels:
            if isinstance(ch, discord.TextChannel):
                results.append(ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.TEXT, category_id=ch.category_id, topic=ch.topic, position=ch.position))
            elif isinstance(ch, discord.VoiceChannel):
                results.append(ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.VOICE, category_id=ch.category_id, position=ch.position))
            elif isinstance(ch, discord.CategoryChannel):
                results.append(ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.CATEGORY, position=ch.position))
        return results

    async def get_categories(self) -> list[CategoryInfo]:
        return [CategoryInfo(id=cat.id, name=cat.name, position=cat.position) for cat in self.guild.categories]

    async def get_roles(self) -> list[RoleInfo]:
        return [
            RoleInfo(id=r.id, name=r.name, permissions=r.permissions.value, position=r.position, managed=r.managed, is_default=r.is_default())
            for r in self.guild.roles
        ]

    async def get_member(self, user_id: int) -> MemberInfo | None:
        m = self.guild.get_member(user_id)
        if not m:
            return None
        return MemberInfo(
            id=m.id,
            name=m.name,
            display_name=m.display_name,
            role_ids=[r.id for r in m.roles],
            is_bot=m.bot,
            is_admin=m.guild_permissions.administrator,
            is_owner=(m.id == self.guild.owner_id),
        )

    async def create_text_channel(self, name: str, *, category_id: int | None = None, topic: str | None = None) -> ChannelInfo:
        category = self.guild.get_channel(category_id) if category_id else None
        ch = await self.guild.create_text_channel(name, category=category, topic=topic, reason="Seromod Agent Action")
        return ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.TEXT, category_id=ch.category_id, topic=ch.topic, position=ch.position)

    async def create_voice_channel(self, name: str, *, category_id: int | None = None) -> ChannelInfo:
        category = self.guild.get_channel(category_id) if category_id else None
        ch = await self.guild.create_voice_channel(name, category=category, reason="Seromod Agent Action")
        return ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.VOICE, category_id=ch.category_id, position=ch.position)

    async def create_category(self, name: str) -> CategoryInfo:
        cat = await self.guild.create_category(name, reason="Seromod Agent Action")
        return CategoryInfo(id=cat.id, name=cat.name, position=cat.position)

    async def create_role(self, name: str) -> RoleInfo:
        r = await self.guild.create_role(name=name, reason="Seromod Agent Action")
        return RoleInfo(id=r.id, name=r.name, permissions=r.permissions.value, position=r.position, managed=r.managed)

    async def edit_channel(self, channel_id: int, *, name: str | None = None, category_id: int | None = None, topic: str | None = None) -> ChannelInfo:
        ch = self.guild.get_channel(channel_id)
        kwargs = {}
        if name: kwargs["name"] = name
        if category_id: kwargs["category"] = self.guild.get_channel(category_id)
        if topic: kwargs["topic"] = topic
        await ch.edit(**kwargs, reason="Seromod Agent Action")
        return ChannelInfo(id=ch.id, name=ch.name, channel_type=ChannelType.TEXT, category_id=ch.category_id, topic=getattr(ch, "topic", None))

    async def delete_channel(self, channel_id: int) -> None:
        ch = self.guild.get_channel(channel_id)
        if ch:
            await ch.delete(reason="Seromod Agent Action")

    async def edit_category(self, category_id: int, *, name: str) -> CategoryInfo:
        cat = self.guild.get_channel(category_id)
        await cat.edit(name=name, reason="Seromod Agent Action")
        return CategoryInfo(id=cat.id, name=cat.name)

    async def delete_category(self, category_id: int) -> None:
        cat = self.guild.get_channel(category_id)
        if cat:
            await cat.delete(reason="Seromod Agent Action")

    async def edit_role(self, role_id: int, *, name: str) -> RoleInfo:
        r = self.guild.get_role(role_id)
        await r.edit(name=name, reason="Seromod Agent Action")
        return RoleInfo(id=r.id, name=r.name)

    async def delete_role(self, role_id: int) -> None:
        r = self.guild.get_role(role_id)
        if r:
            await r.delete(reason="Seromod Agent Action")

    async def send_message(self, channel_id: int, content: str) -> MessageInfo:
        ch = self.guild.get_channel(channel_id)
        msg = await ch.send(content)
        return MessageInfo(id=msg.id, channel_id=msg.channel.id, author_id=msg.author.id, content=msg.content, timestamp=msg.created_at.timestamp())

    async def timeout_member(self, user_id: int, duration_seconds: int, reason: str) -> None:
        m = self.guild.get_member(user_id)
        if m:
            from datetime import timedelta
            await m.timeout(discord.utils.utcnow() + timedelta(seconds=duration_seconds), reason=reason)

    async def kick_member(self, user_id: int, reason: str) -> None:
        m = self.guild.get_member(user_id)
        if m:
            await m.kick(reason=reason)

    async def ban_member(self, user_id: int, reason: str) -> None:
        m = self.guild.get_member(user_id)
        if m:
            await m.ban(reason=reason)


def build_agent_system() -> tuple[AgentRuntime, ToolRegistry, WorkspaceMemoryStore, ModerationSkill]:
    workspace = WorkspaceMemoryStore(base_dir=os.getenv("SEROMOD_WORKSPACE_DIR", "workspace/guilds"))
    policy = PolicyEngine()
    brain = GeminiBrain(api_key=config.gemini_api_key, model_name=config.gemini_model)

    tools = ToolRegistry()
    tools.register(GetChannelsTool())
    tools.register(CreateChannelTool())
    tools.register(DeleteChannelTool())
    tools.register(GetCategoriesTool())
    tools.register(CreateCategoryTool())
    tools.register(GetRolesTool())
    tools.register(CreateRoleTool())
    tools.register(GetServerStateTool())
    tools.register(SendMessageTool())
    tools.register(TimeoutMemberTool())
    tools.register(KickMemberTool())
    tools.register(BanMemberTool())
    tools.register(SearchDecisionsTool(workspace))
    tools.register(MemoryReadTool(workspace))
    tools.register(MemoryWriteTool(workspace))
    tools.register(MemorySearchTool(workspace))
    tools.register(MemoryUpdateTool(workspace))

    runtime = AgentRuntime(brain, tools, workspace, policy)
    mod_skill = ModerationSkill(brain, tools, workspace, policy)
    return runtime, tools, workspace, mod_skill


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    intents.members = True

    bot = discord.Client(intents=intents)
    runtime, tools, workspace, mod_skill = build_agent_system()

    @bot.event
    async def on_ready():
        log.info("Seromod Agent is live as %s (ID: %s)", bot.user.name, bot.user.id)

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_handle = DiscordGuildWrapper(message.guild)
        author_info = await guild_handle.get_member(message.author.id)
        if not author_info:
            return

        # 1. Moderation Event Pipeline
        msg_info = MessageInfo(
            id=message.id,
            channel_id=message.channel.id,
            author_id=message.author.id,
            content=message.content,
            timestamp=message.created_at.timestamp(),
        )
        mod_result = await mod_skill.handle_message_event(msg_info, author_info, guild_handle)
        if mod_result.get("action_taken") in ("timeout", "kick", "ban"):
            await message.channel.send(f"⚠️ Action taken against {message.author.mention}: {mod_result.get('reason')}")
            return

        # 2. Check if Seromod is addressed / mentioned
        if bot.user in message.mentions:
            clean_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if not clean_text:
                await message.channel.send("Hello! I am Seromod, your AI server administrator. How can I help you?")
                return

            lower_query = clean_text.lower()
            if any(term in lower_query for term in ("build", "create server", "setup server", "make this server", "organize")):
                skill = ServerBuilderSkill()
                task_type = "server_build"
            else:
                skill = ConversationSkill()
                task_type = "conversation"

            task = AgentTask(
                task_type=task_type,
                goal=clean_text,
                guild_id=message.guild.id,
                created_by=message.author.id,
            )

            async with message.channel.typing():
                res_task = await runtime.execute_task(
                    task=task,
                    guild=guild_handle,
                    skill=skill,
                    user_message=clean_text,
                    caller=author_info,
                )

            if res_task.status == TaskStatus.WAITING_FOR_APPROVAL and res_task.pending_approval:
                await message.channel.send(
                    f"⚠️ **Approval Required**: Seromod requested high-impact action `{res_task.pending_approval.tool}`.\n"
                    f"Reason: {res_task.pending_approval.reason}\n"
                    f"Arguments: `{res_task.pending_approval.arguments}`\n"
                    "Reply `!approve` to proceed."
                )
            else:
                await message.channel.send(res_task.result_message or "Task finished.")

    if not config.discord_token:
        log.warning("No DISCORD_TOKEN set. Cannot connect to live Discord gateway. Exiting.")
        return

    bot.run(config.discord_token)


if __name__ == "__main__":
    run()
