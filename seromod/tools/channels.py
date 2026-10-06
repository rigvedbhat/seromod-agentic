from __future__ import annotations

import re
from typing import Any

from seromod.guild_handle import ChannelType, GuildHandle
from seromod.tools.base import Tool, ToolResult

CHANNEL_NAME_RE = re.compile(r"^[a-z0-9-]{1,48}$")


def clean_channel_name(name: str) -> str:
    cleaned = name.strip().lower().replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9-]", "", cleaned)
    return cleaned[:48]


class GetChannelsTool(Tool):
    name = "get_channels"
    description = "List all existing channels and categories in the Discord server."
    parameters = {"type": "object", "properties": {}}
    requires_permission = "view_channel"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        channels = await guild.get_channels()
        categories = await guild.get_categories()
        data = {
            "categories": [{"id": c.id, "name": c.name} for c in categories],
            "channels": [
                {
                    "id": ch.id,
                    "name": ch.name,
                    "type": ch.channel_type.value,
                    "category_id": ch.category_id,
                    "topic": ch.topic,
                }
                for ch in channels
            ],
        }
        return ToolResult(success=True, data=data)


class CreateChannelTool(Tool):
    name = "create_channel"
    description = "Create a new text or voice channel in the Discord server."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Channel name (lowercase, alphanumeric with hyphens)"},
            "channel_type": {"type": "string", "enum": ["text", "voice"], "default": "text"},
            "category_name": {"type": "string", "description": "Optional category name to place channel under"},
            "topic": {"type": "string", "description": "Optional channel topic/description"},
        },
        "required": ["name"],
    }
    requires_permission = "manage_channels"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        name = clean_channel_name(args["name"])
        if not name:
            return ToolResult(success=False, error="Invalid channel name.")

        # Check existing channels to avoid duplicates
        existing = await guild.get_channels()
        for ch in existing:
            if ch.name.lower() == name.lower():
                return ToolResult(
                    success=True,
                    data={"id": ch.id, "name": ch.name, "already_exists": True},
                )

        # Resolve category if specified
        category_id: int | None = None
        category_name = args.get("category_name")
        if category_name:
            categories = await guild.get_categories()
            for cat in categories:
                if cat.name.lower() == category_name.strip().lower():
                    category_id = cat.id
                    break
            if category_id is None:
                # Automatically create the category if missing
                new_cat = await guild.create_category(category_name.strip())
                category_id = new_cat.id

        channel_type = args.get("channel_type", "text")
        topic = args.get("topic")

        try:
            if channel_type == "voice":
                ch = await guild.create_voice_channel(name, category_id=category_id)
            else:
                ch = await guild.create_text_channel(name, category_id=category_id, topic=topic)

            return ToolResult(
                success=True,
                data={"id": ch.id, "name": ch.name, "type": ch.channel_type.value, "category_id": ch.category_id},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class DeleteChannelTool(Tool):
    name = "delete_channel"
    description = "Delete a channel from the Discord server. HIGH IMPACT: requires explicit approval."
    parameters = {
        "type": "object",
        "properties": {
            "channel_name": {"type": "string", "description": "Name of the channel to delete"},
            "channel_id": {"type": "integer", "description": "Optional channel ID"},
        },
    }
    requires_permission = "manage_channels"
    high_impact = True  # Triggers WAITING_FOR_APPROVAL

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        channels = await guild.get_channels()
        target_id = args.get("channel_id")
        target_name = args.get("channel_name", "").lower()

        target = None
        for ch in channels:
            if target_id and ch.id == target_id:
                target = ch
                break
            if target_name and ch.name.lower() == target_name:
                target = ch
                break

        if not target:
            return ToolResult(success=False, error=f"Channel '{target_name or target_id}' not found.")

        # Protected channels
        if target.name == "seromod-instructions":
            return ToolResult(success=False, error="Protected channel 'seromod-instructions' cannot be deleted.")

        try:
            await guild.delete_channel(target.id)
            return ToolResult(success=True, data={"deleted_channel": target.name, "id": target.id})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
