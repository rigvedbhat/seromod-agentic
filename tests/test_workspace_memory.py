from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from seromod.agent.context import build_server_context
from seromod.agent.decisions import (
    AgentDecision,
    DecisionAction,
    ModerationAnalysisResult,
    ModerationEvidence,
    ToolCallRequest,
)
from seromod.agent.runtime import AgentRuntime
from seromod.agent.task import AgentTask, TaskStatus
from seromod.guild_handle import MemberInfo, MessageInfo
from seromod.memory.decisions import DecisionRecord
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.policy.engine import PolicyEngine
from seromod.skills.conversation import ConversationSkill
from seromod.skills.moderation import ModerationSkill
from seromod.skills.server_builder import ServerBuilderSkill
from seromod.tools.categories import CreateCategoryTool, GetCategoriesTool
from seromod.tools.channels import CreateChannelTool, DeleteChannelTool, GetChannelsTool
from seromod.tools.members import TimeoutMemberTool
from seromod.tools.memory_tools import SearchDecisionsTool
from seromod.tools.registry import ToolRegistry
from seromod.tools.roles import CreateRoleTool, GetRolesTool
from seromod.tools.server import GetServerStateTool
from seromod.tools.workspace_memory import (
    MemoryReadTool,
    MemorySearchTool,
    MemoryUpdateTool,
    MemoryWriteTool,
)
from tests.fake_brain import FakeBrain
from tests.fake_discord import FakeGuild


class TestSeromodWorkspaceMemory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace" / "guilds"
        self.workspace = WorkspaceMemoryStore(base_dir=self.workspace_dir)
        self.policy_engine = PolicyEngine()
        self.fake_guild = FakeGuild(guild_id=444, name="Test Guild")

        self.registry = ToolRegistry()
        self.registry.register(GetChannelsTool())
        self.registry.register(CreateChannelTool())
        self.registry.register(DeleteChannelTool())
        self.registry.register(GetCategoriesTool())
        self.registry.register(CreateCategoryTool())
        self.registry.register(GetRolesTool())
        self.registry.register(CreateRoleTool())
        self.registry.register(GetServerStateTool())
        self.registry.register(TimeoutMemberTool())
        self.registry.register(SearchDecisionsTool(self.workspace))
        self.registry.register(MemoryReadTool(self.workspace))
        self.registry.register(MemoryWriteTool(self.workspace))
        self.registry.register(MemorySearchTool(self.workspace))
        self.registry.register(MemoryUpdateTool(self.workspace))

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_1_agent_writes_memory(self):
        """1. The agent can write a memory using memory_write or memory_update tool."""
        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(
                        tool="memory_write",
                        arguments={
                            "filename": "MEMORY.md",
                            "content": "- Note: Community hosts game night every Friday at 8 PM.",
                            "append": True,
                        },
                    ),
                ],
                reasoning="Record Friday game night preference",
            )
        )
        fake_brain.queue_decision(
            AgentDecision(action=DecisionAction.FINISH, response="Recorded memory note.")
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(task_type="conversation", goal="Remember game night", guild_id=self.fake_guild.guild_id)

        res = await runtime.execute_task(task, self.fake_guild, ConversationSkill(), "Remember that game night is Friday at 8 PM.")
        self.assertEqual(res.status, TaskStatus.COMPLETED)

        # Inspect disk directly
        mem_text = await self.workspace.read_doc(self.fake_guild.guild_id, "MEMORY.md")
        self.assertIn("Friday at 8 PM", mem_text)

    async def test_2_and_3_memory_survives_restart_and_retrieved_in_later_session(self):
        """2. Memory survives a process restart.

        3. The agent can retrieve the memory in a later session.
        """
        # Session 1: Write preference to SERVER.md
        await self.workspace.append_doc(
            self.fake_guild.guild_id,
            "SERVER.md",
            "- Admin Preference: Strict Minecraft SMP with no PvP allowed in spawn.\n",
        )

        # SIMULATE PROCESS RESTART: create brand new WorkspaceMemoryStore instance pointing to same disk
        restarted_workspace = WorkspaceMemoryStore(base_dir=self.workspace_dir)
        restarted_registry = ToolRegistry()
        restarted_registry.register(MemoryReadTool(restarted_workspace))
        restarted_registry.register(MemorySearchTool(restarted_workspace))

        # Session 2: User asks "What is the policy on spawn PvP?"
        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="memory_search", arguments={"query": "spawn"}),
                ],
                reasoning="Search memory workspace for spawn rules",
            )
        )
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.RESPOND,
                response="According to SERVER.md preferences, spawn is strictly non-PvP.",
            )
        )

        runtime_v2 = AgentRuntime(fake_brain, restarted_registry, restarted_workspace, self.policy_engine)
        task = AgentTask(task_type="conversation", goal="Recall spawn rule", guild_id=self.fake_guild.guild_id)

        res = await runtime_v2.execute_task(task, self.fake_guild, ConversationSkill(), "Can players fight in spawn?")
        self.assertEqual(res.status, TaskStatus.COMPLETED)
        self.assertIn("non-PvP", res.result_message or "")

    async def test_4_and_5_deleted_discord_channel_recognized_as_deleted_even_if_memory_says_created(self):
        """4. The agent does not use stale memory as the source of truth for current Discord state.

        5. A deleted Discord channel is recognized as deleted even if memory says Seromod originally created it.
        """
        # Step A: Record historical creation of #tournaments in DECISIONS.md
        await self.workspace.record_decision(
            self.fake_guild.guild_id,
            DecisionRecord(
                guild_id=self.fake_guild.guild_id,
                entity_type="channel",
                action="create_channel",
                entity_name="tournaments",
                reason="Created for competitive weekend tournaments",
                requested_by=101,
                task_id="task_old_99",
            ),
        )

        # BUT: Ensure #tournaments does NOT exist in live Discord (fake_guild)
        live_channels = await self.fake_guild.get_channels()
        self.assertFalse(any(c.name == "tournaments" for c in live_channels))

        # Check ServerContext directly: live channels must NOT have #tournaments
        ctx = await build_server_context(self.fake_guild, self.workspace)
        self.assertFalse(any(c.name == "tournaments" for c in ctx.live_channels))

        # Ask: "Does #tournaments exist currently?"
        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.RESPOND,
                response="No, #tournaments does not currently exist on the server. Although my historical records indicate I created it in task_old_99, it has since been deleted from Discord.",
            )
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(task_type="conversation", goal="Check channel existence", guild_id=self.fake_guild.guild_id)

        res = await runtime.execute_task(task, self.fake_guild, ConversationSkill(), "Does #tournaments exist currently?")
        self.assertEqual(res.status, TaskStatus.COMPLETED)
        self.assertIn("does not currently exist", res.result_message or "")

    async def test_6_answers_why_it_originally_created_channel_from_decisions_md(self):
        """6. The agent can answer why it originally created that channel from DECISIONS.md."""
        # Record creation of #marketplace in DECISIONS.md
        await self.workspace.record_decision(
            self.fake_guild.guild_id,
            DecisionRecord(
                guild_id=self.fake_guild.guild_id,
                entity_type="channel",
                action="create_channel",
                entity_name="marketplace",
                reason="Provide a designated trade hub for players to barter items without spamming general",
                requested_by=202,
                task_id="task_build_55",
            ),
        )

        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="search_decisions", arguments={"entity_name": "marketplace"}),
                ],
                reasoning="Look up reason for #marketplace creation in DECISIONS.md",
            )
        )
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.RESPOND,
                response="According to DECISIONS.md, I created #marketplace to provide a designated trade hub for players to barter items without spamming general chat (Task ID: task_build_55).",
            )
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(task_type="conversation", goal="Explain marketplace", guild_id=self.fake_guild.guild_id)

        res = await runtime.execute_task(task, self.fake_guild, ConversationSkill(), "Why did you create #marketplace?")
        self.assertEqual(res.status, TaskStatus.COMPLETED)
        self.assertIn("trade hub", res.result_message or "")


if __name__ == "__main__":
    unittest.main()
