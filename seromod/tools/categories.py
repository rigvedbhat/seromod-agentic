from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.tools.base import Tool, ToolResult


class GetCategoriesTool(Tool):
    name = "get_categories"
    description = "List all existing category channels in the Discord server."
    parameters = {"type": "object", "properties": {}}
    requires_permission = "view_channel"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        categories = await guild.get_categories()
        return ToolResult(
            success=True,
            data=[{"id": c.id, "name": c.name} for c in categories],
        )


class CreateCategoryTool(Tool):
    name = "create_category"
    description = "Create a new category for organizing channels in the Discord server."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The category name (e.g. 'Community', 'Gaming')"},
        },
        "required": ["name"],
    }
    requires_permission = "manage_channels"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        name = args["name"].strip()
        if not name:
            return ToolResult(success=False, error="Category name cannot be empty.")

        existing = await guild.get_categories()
        for cat in existing:
            if cat.name.lower() == name.lower():
                return ToolResult(
                    success=True,
                    data={"id": cat.id, "name": cat.name, "already_exists": True},
                )

        try:
            cat = await guild.create_category(name)
            return ToolResult(success=True, data={"id": cat.id, "name": cat.name})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
