from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from seromod.guild_handle import CategoryInfo, ChannelInfo, GuildHandle, RoleInfo
from seromod.memory.decisions import DecisionRecord
from seromod.memory.workspace import WorkspaceMemoryStore


@dataclass
class ServerContext:
    """The agent's understanding of the server.

    CRITICAL PRINCIPLE:
    - Live Discord state is the EXCLUSIVE authoritative source of truth for current server channels,
      roles, and categories.
    - Local workspace memory is the historical context layer (identifying reasons, preferences, and logs).
    - If a channel is deleted from Discord, it is gone, regardless of what DECISIONS.md or MEMORY.md says.
    """

    guild_id: int
    guild_name: str

    # 1. LIVE DISCORD STATE (AUTHORITATIVE)
    live_categories: list[CategoryInfo] = field(default_factory=list)
    live_channels: list[ChannelInfo] = field(default_factory=list)
    live_roles: list[RoleInfo] = field(default_factory=list)

    # 2. CORE WORKSPACE DOCUMENTS (LOADED AT START OF SESSION)
    agent_persona: str = ""       # from AGENTS.md
    server_info: str = ""         # from SERVER.md
    core_memory: str = ""         # from MEMORY.md
    policy_info: str = ""         # from POLICY.md

    # 3. SELECTIVE HISTORICAL RETRIEVAL
    recent_decisions: list[DecisionRecord] = field(default_factory=list)
    today_notes: str = ""         # from memory/YYYY-MM-DD.md if relevant

    def summary(self) -> str:
        """Construct the prompt context carefully separating live Discord truth from workspace memory."""
        cat_names = [c.name for c in self.live_categories]
        ch_names = [f"#{c.name}" for c in self.live_channels if c.channel_type.value != "category"]
        role_names = [r.name for r in self.live_roles if not r.is_default]

        sections = [
            "=== LIVE DISCORD SERVER STATE (AUTHORITATIVE SOURCE OF TRUTH) ===",
            f"Server: {self.guild_name} (ID: {self.guild_id})",
            f"Categories ({len(cat_names)}): {', '.join(cat_names) if cat_names else 'None'}",
            f"Active Channels ({len(ch_names)}): {', '.join(ch_names[:30])}{'...' if len(ch_names) > 30 else ''}",
            f"Roles ({len(role_names)}): {', '.join(role_names[:25])}{'...' if len(role_names) > 25 else ''}",
            "\n=== LOCAL AGENT WORKSPACE MEMORY (DERIVED CONTEXT & HISTORY) ===",
        ]

        if self.server_info:
            sections.append(f"--- SERVER.md ---\n{self.server_info.strip()}")

        if self.policy_info:
            sections.append(f"--- POLICY.md ---\n{self.policy_info.strip()}")

        if self.recent_decisions:
            sections.append("--- RECENT DECISIONS (from DECISIONS.md) ---")
            for d in self.recent_decisions[:5]:
                sections.append(f"- [{d.action.upper()} {d.entity_type} '{d.entity_name}']: {d.reason}")

        if self.today_notes:
            sections.append(f"--- TODAY'S LOG ---\n{self.today_notes.strip()}")

        return "\n\n".join(sections)


async def build_server_context(
    guild: GuildHandle,
    workspace: WorkspaceMemoryStore,
    *,
    decision_limit: int = 10,
    entity_name_filter: str | None = None,
    load_daily_notes: bool = False,
) -> ServerContext:
    """Builds ServerContext:

    1. Fetches live authoritative Discord state from GuildHandle.
    2. Loads core workspace files: AGENTS.md, SERVER.md, MEMORY.md, POLICY.md.
    3. Retrieves DECISIONS.md or daily notes only when relevant.
    """
    # 1. Authoritative Discord Query
    channels = await guild.get_channels()
    categories = await guild.get_categories()
    roles = await guild.get_roles()

    # 2. Core Workspace Documents
    agents_doc = await workspace.read_doc(guild.guild_id, "AGENTS.md")
    server_doc = await workspace.read_doc(guild.guild_id, "SERVER.md")
    memory_doc = await workspace.read_doc(guild.guild_id, "MEMORY.md")
    policy_doc = await workspace.read_doc(guild.guild_id, "POLICY.md")

    # 3. Selective Historical Context
    decisions = await workspace.get_decisions(
        guild.guild_id,
        limit=decision_limit,
        entity_name=entity_name_filter,
    )

    today_str = datetime.date.today().isoformat()
    daily_notes = await workspace.read_daily_note(guild.guild_id, today_str) if load_daily_notes else ""

    return ServerContext(
        guild_id=guild.guild_id,
        guild_name=guild.name,
        live_categories=categories,
        live_channels=channels,
        live_roles=roles,
        agent_persona=agents_doc,
        server_info=server_doc,
        core_memory=memory_doc,
        policy_info=policy_doc,
        recent_decisions=decisions,
        today_notes=daily_notes,
    )
