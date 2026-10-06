from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.tools.base import Tool, ToolResult


class SearchDecisionsTool(Tool):
    name = "search_decisions"
    description = "Search historical decision logs in DECISIONS.md for past actions taken by Seromod."
    parameters = {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string", "description": "Optional name of channel/role to look up"},
            "entity_type": {"type": "string", "description": "Optional entity type (e.g. 'channel', 'role')"},
            "limit": {"type": "integer", "default": 10},
        },
    }
    requires_permission = "view_channel"
    high_impact = False

    def __init__(self, workspace: WorkspaceMemoryStore):
        self.workspace = workspace

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        records = await self.workspace.get_decisions(
            guild.guild_id,
            limit=args.get("limit", 10),
            entity_type=args.get("entity_type"),
            entity_name=args.get("entity_name"),
        )
        return ToolResult(
            success=True,
            data=[r.to_dict() for r in records],
        )
