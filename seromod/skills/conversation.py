from __future__ import annotations

from seromod.agent.context import ServerContext
from seromod.skills.base import Skill
from seromod.tools.base import Tool
from seromod.tools.registry import ToolRegistry


class ConversationSkill(Skill):
    name = "conversation"
    description = "Answers questions about the server, historical decisions, roles, channels, and admin preferences using live state and workspace memory."

    def system_prompt(self, context: ServerContext) -> str:
        return f"""You are Seromod, the AI Administrator of this Discord server.

CORE ARCHITECTURAL RULES:
1. LIVE DISCORD STATE IS THE SOLE AUTHORITATIVE SOURCE OF TRUTH for current channels, roles, and categories.
   - If asked "Does #channel exist?", check the Live Discord State.
   - If a channel is NOT in the Live Discord State, it DOES NOT exist right now (even if mentioned in DECISIONS.md or MEMORY.md).
2. WORKSPACE MEMORY IS THE CONTEXT & REASONING LAYER:
   - If asked "Why did you create #channel?", consult DECISIONS.md via `search_decisions` or `memory_read`.
   - If asked "What is the server purpose?" or "What does the admin prefer?", consult SERVER.md or `memory_read`.
   - Never hallucinate past actions. If there is no record in DECISIONS.md, state that you have no record of creating it.
3. You can read and write your workspace memory using: `memory_read`, `memory_write`, `memory_search`, `memory_update`.

{context.summary()}
"""

    def get_tools(self, registry: ToolRegistry) -> list[Tool]:
        tool_names = [
            "search_decisions",
            "memory_read",
            "memory_write",
            "memory_search",
            "memory_update",
            "get_server_state",
            "get_channels",
            "get_roles",
        ]
        return [t for name in tool_names if (t := registry.get(name))]
