from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.tools.base import Tool, ToolResult


class GetServerStateTool(Tool):
    name = "get_server_state"
    description = "Inspect the full live structure of the server: categories, channels, and roles."
    parameters = {"type": "object", "properties": {}}
    requires_permission = "view_channel"
    high_impact = False

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        channels = await guild.get_channels()
        categories = await guild.get_categories()
        roles = await guild.get_roles()

        cat_map = {c.id: c.name for c in categories}
        organized: dict[str, list[str]] = {"Uncategorized": []}
        for c in categories:
            organized[c.name] = []

        for ch in channels:
            if ch.channel_type.value == "category":
                continue
            cat_name = cat_map.get(ch.category_id, "Uncategorized")
            if cat_name not in organized:
                organized[cat_name] = []
            organized[cat_name].append(f"#{ch.name} ({ch.channel_type.value})")

        return ToolResult(
            success=True,
            data={
                "server_name": guild.name,
                "structure": organized,
                "roles": [r.name for r in roles if not r.is_default],
            },
        )
