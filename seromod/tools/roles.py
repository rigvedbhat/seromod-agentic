from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.tools.base import Tool, ToolResult


class GetRolesTool(Tool):
    name = "get_roles"
    description = "List all existing roles in the Discord server."
    parameters = {"type": "object", "properties": {}}
    requires_permission = "view_channel"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        roles = await guild.get_roles()
        return ToolResult(
            success=True,
            data=[{"id": r.id, "name": r.name, "managed": r.managed} for r in roles if not r.is_default],
        )


class CreateRoleTool(Tool):
    name = "create_role"
    description = "Create a new role in the Discord server (e.g. 'Moderator', 'VIP')."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name of the role to create"},
        },
        "required": ["name"],
    }
    requires_permission = "manage_roles"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        name = args["name"].strip()
        if not name:
            return ToolResult(success=False, error="Role name cannot be empty.")

        existing = await guild.get_roles()
        for r in existing:
            if r.name.lower() == name.lower():
                return ToolResult(
                    success=True,
                    data={"id": r.id, "name": r.name, "already_exists": True},
                )

        try:
            role = await guild.create_role(name)
            return ToolResult(success=True, data={"id": role.id, "name": role.name})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
