from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.tools.base import Tool, ToolResult


class TimeoutMemberTool(Tool):
    name = "timeout_member"
    description = "Place a member in timeout (isolate/mute) for a duration in seconds."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "The Discord ID of the user"},
            "duration_seconds": {"type": "integer", "description": "Timeout duration in seconds (e.g. 60, 300)"},
            "reason": {"type": "string", "description": "Reason for timeout"},
        },
        "required": ["user_id", "duration_seconds", "reason"],
    }
    requires_permission = "moderate_members"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        try:
            await guild.timeout_member(int(args["user_id"]), int(args["duration_seconds"]), str(args["reason"]))
            return ToolResult(success=True, data={"timed_out_user": args["user_id"], "duration": args["duration_seconds"]})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class KickMemberTool(Tool):
    name = "kick_member"
    description = "Kick a member from the Discord server. HIGH IMPACT: requires explicit approval."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "The Discord ID of the user"},
            "reason": {"type": "string", "description": "Reason for kicking the user"},
        },
        "required": ["user_id", "reason"],
    }
    requires_permission = "kick_members"
    high_impact = True  # Triggers WAITING_FOR_APPROVAL

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        try:
            await guild.kick_member(int(args["user_id"]), str(args["reason"]))
            return ToolResult(success=True, data={"kicked_user": args["user_id"]})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BanMemberTool(Tool):
    name = "ban_member"
    description = "Ban a member from the Discord server. HIGH IMPACT: requires explicit approval."
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "The Discord ID of the user"},
            "reason": {"type": "string", "description": "Reason for banning the user"},
        },
        "required": ["user_id", "reason"],
    }
    requires_permission = "ban_members"
    high_impact = True  # Triggers WAITING_FOR_APPROVAL

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        try:
            await guild.ban_member(int(args["user_id"]), str(args["reason"]))
            return ToolResult(success=True, data={"banned_user": args["user_id"]})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
