from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.tools.base import Tool, ToolResult


class SendMessageTool(Tool):
    name = "send_message"
    description = "Send a text message to a specific channel in the Discord server."
    parameters = {
        "type": "object",
        "properties": {
            "channel_id": {"type": "integer", "description": "The channel ID to send to"},
            "content": {"type": "string", "description": "Message content to post"},
        },
        "required": ["channel_id", "content"],
    }
    requires_permission = "send_messages"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        ch_id = int(args["channel_id"])
        content = str(args["content"])
        try:
            msg = await guild.send_message(ch_id, content)
            return ToolResult(success=True, data={"message_id": msg.id, "channel_id": ch_id})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
