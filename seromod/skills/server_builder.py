from __future__ import annotations

from seromod.agent.context import ServerContext
from seromod.skills.base import Skill
from seromod.tools.base import Tool
from seromod.tools.registry import ToolRegistry


class ServerBuilderSkill(Skill):
    name = "server_builder"
    description = "Inspects server, plans desired structure, and executes channel/role creation."

    def system_prompt(self, context: ServerContext) -> str:
        return f"""You are Seromod, an expert AI Discord Server Architect.
Your task is to build or modify the server based on the user's requested theme.

Rules:
1. Examine the CURRENT LIVE DISCORD STATE below. Do NOT duplicate existing channels or categories.
2. Build categories first, then text and voice channels under those categories.
3. Be methodical: call tools one or a few at a time.
4. When finished, summarize what you created and provide suggestions for next steps.

{context.summary()}
"""

    def get_tools(self, registry: ToolRegistry) -> list[Tool]:
        tool_names = ["create_category", "create_channel", "create_role", "get_channels", "get_server_state", "delete_channel"]
        return [t for name in tool_names if (t := registry.get(name))]
