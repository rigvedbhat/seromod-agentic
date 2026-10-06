from __future__ import annotations

import asyncio
import datetime
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from seromod.agent.task import AgentTask
from seromod.memory.decisions import DecisionRecord

log = logging.getLogger("seromod.memory.workspace")


class WorkspaceMemoryStore:
    """Per-guild local agent workspace memory inspired by Hermes and OpenClaw.

    Structure:
    workspace/
    └── guilds/
        └── {guild_id}/
            ├── AGENTS.md        # Agent persona, identity & guidelines
            ├── SERVER.md        # Purpose, theme, administrator preferences
            ├── MEMORY.md        # Long-term curated knowledge & facts
            ├── DECISIONS.md     # Chronological log of major decisions & rationale
            ├── POLICY.md        # Natural language moderation & server policies
            ├── memory/          # Daily notes/logs: YYYY-MM-DD.md
            │   └── YYYY-MM-DD.md
            ├── sessions/        # Session conversation histories (JSON)
            └── tasks/           # Machine state for active/past tasks (JSON)
    """

    def __init__(self, base_dir: str | Path = "workspace/guilds"):
        self.base_dir = Path(base_dir)
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def guild_dir(self, guild_id: int) -> Path:
        d = self.base_dir / str(guild_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "memory").mkdir(parents=True, exist_ok=True)
        (d / "sessions").mkdir(parents=True, exist_ok=True)
        (d / "tasks").mkdir(parents=True, exist_ok=True)
        return d

    def initialize_guild_defaults(self, guild_id: int, guild_name: str = "") -> None:
        """Seed default workspace Markdown files if they don't exist yet."""
        g_dir = self.guild_dir(guild_id)

        agents_file = g_dir / "AGENTS.md"
        if not agents_file.exists():
            agents_file.write_text(
                f"# AGENTS.md — Seromod Agent Persona\n\n"
                f"- Name: Seromod\n"
                f"- Role: AI Administrator for Discord Server '{guild_name or guild_id}'\n"
                f"- Guiding Principles: Act deliberately, respect server guidelines, explain reasons clearly.\n",
                encoding="utf-8",
            )

        server_file = g_dir / "SERVER.md"
        if not server_file.exists():
            server_file.write_text(
                f"# SERVER.md — Server Purpose & Administrator Preferences\n\n"
                f"- Server ID: {guild_id}\n"
                f"- Name: {guild_name}\n"
                f"- Server Purpose: General community server\n"
                f"- Admin Preferences:\n"
                f"  - Prefer organized categories\n"
                f"  - Protect staff channels\n",
                encoding="utf-8",
            )

        memory_file = g_dir / "MEMORY.md"
        if not memory_file.exists():
            memory_file.write_text(
                f"# MEMORY.md — Long-Term Curated Knowledge\n\n"
                f"Curated facts and notes about server community and operations.\n",
                encoding="utf-8",
            )

        decisions_file = g_dir / "DECISIONS.md"
        if not decisions_file.exists():
            decisions_file.write_text(
                f"# DECISIONS.md — Historical Decision Log\n\n"
                f"Chronological record of significant configuration changes, channel/role creations, and moderation actions.\n\n",
                encoding="utf-8",
            )

        policy_file = g_dir / "POLICY.md"
        if not policy_file.exists():
            policy_file.write_text(
                f"# POLICY.md — Moderation & Governance Policies\n\n"
                f"- profanity: warn\n"
                f"- harassment: timeout\n"
                f"- spam: timeout\n"
                f"- mass_actions: requires_approval\n",
                encoding="utf-8",
            )

    # ---------------------------------------------------------
    # Core Document Access (AGENTS, SERVER, MEMORY, POLICY, DECISIONS)
    # ---------------------------------------------------------

    async def read_doc(self, guild_id: int, filename: str) -> str:
        """Read a top-level workspace markdown file (e.g. 'SERVER.md', 'DECISIONS.md')."""
        self.initialize_guild_defaults(guild_id)
        path = self.guild_dir(guild_id) / filename
        if not path.exists():
            return ""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_text, path)

    async def write_doc(self, guild_id: int, filename: str, content: str) -> None:
        """Overwrite a top-level workspace markdown file."""
        self.initialize_guild_defaults(guild_id)
        path = self.guild_dir(guild_id) / filename
        async with self._get_lock(f"file_{guild_id}_{filename}"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_text, path, content)

    async def append_doc(self, guild_id: int, filename: str, content: str) -> None:
        """Append text to a top-level workspace markdown file."""
        self.initialize_guild_defaults(guild_id)
        path = self.guild_dir(guild_id) / filename
        async with self._get_lock(f"file_{guild_id}_{filename}"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._append_text, path, content)

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def _append_text(self, path: Path, content: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

    # ---------------------------------------------------------
    # Daily Notes (memory/YYYY-MM-DD.md)
    # ---------------------------------------------------------

    async def append_daily_note(self, guild_id: int, note: str, date_str: str | None = None) -> None:
        """Append an observation to the daily markdown note (memory/YYYY-MM-DD.md)."""
        self.initialize_guild_defaults(guild_id)
        if not date_str:
            date_str = datetime.date.today().isoformat()
        filepath = self.guild_dir(guild_id) / "memory" / f"{date_str}.md"
        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"- [{now_time}] {note.strip()}\n"

        async with self._get_lock(f"daily_{guild_id}_{date_str}"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._append_text, filepath, entry)

    async def read_daily_note(self, guild_id: int, date_str: str) -> str:
        filepath = self.guild_dir(guild_id) / "memory" / f"{date_str}.md"
        if not filepath.exists():
            return ""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_text, filepath)

    # ---------------------------------------------------------
    # Decision Recording (DECISIONS.md)
    # ---------------------------------------------------------

    async def record_decision(self, guild_id: int, record: DecisionRecord) -> None:
        """Log an explicit decision to DECISIONS.md."""
        now_iso = datetime.datetime.fromtimestamp(record.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"### [{now_iso}] {record.action.upper()} {record.entity_type} `{record.entity_name}`\n"
            f"- **Reason**: {record.reason}\n"
            f"- **Requested By**: {record.requested_by or 'Autonomous / Agent'}\n"
            f"- **Task ID**: {record.task_id or 'none'}\n\n"
        )
        await self.append_doc(guild_id, "DECISIONS.md", entry)

    async def get_decisions(
        self,
        guild_id: int,
        *,
        limit: int = 20,
        entity_name: str | None = None,
        entity_type: str | None = None,
    ) -> list[DecisionRecord]:
        """Read and parse DECISIONS.md into DecisionRecord models."""
        content = await self.read_doc(guild_id, "DECISIONS.md")
        if not content:
            return []

        records: list[DecisionRecord] = []
        blocks = content.split("### ")
        for block in reversed(blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            header = lines[0]  # "[2026-10-03 18:20:00] CREATE_CHANNEL `channel-name`"
            try:
                parts = header.split("] ", 1)
                time_str = parts[0].replace("[", "").strip() if len(parts) > 1 else ""
                action_part = parts[1] if len(parts) > 1 else parts[0]

                action_words = action_part.split(" ")
                action = action_words[0] if len(action_words) > 0 else "action"
                etype = action_words[1] if len(action_words) > 1 else "entity"
                ename = action_words[2].replace("`", "") if len(action_words) > 2 else ""

                reason = ""
                requested_by = None
                task_id = None
                for line in lines[1:]:
                    if line.startswith("- **Reason**:"):
                        reason = line.replace("- **Reason**:", "").strip()
                    elif line.startswith("- **Requested By**:"):
                        req_str = line.replace("- **Requested By**:", "").strip()
                        requested_by = int(req_str) if req_str.isdigit() else None
                    elif line.startswith("- **Task ID**:"):
                        task_id = line.replace("- **Task ID**:", "").strip()

                if entity_name and ename.lower() != entity_name.lower():
                    continue
                if entity_type and etype.lower() != entity_type.lower():
                    continue

                records.append(
                    DecisionRecord(
                        guild_id=guild_id,
                        entity_type=etype,
                        action=action,
                        entity_name=ename,
                        reason=reason,
                        requested_by=requested_by,
                        task_id=task_id,
                    )
                )
                if len(records) >= limit:
                    break
            except Exception:
                continue

        return records

    # ---------------------------------------------------------
    # Search Across Workspace
    # ---------------------------------------------------------

    async def search_workspace(self, guild_id: int, query: str) -> list[dict[str, Any]]:
        """Search across all markdown files in the guild workspace for query snippets."""
        g_dir = self.guild_dir(guild_id)
        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        loop = asyncio.get_running_loop()

        def _do_search():
            matches = []
            for path in g_dir.rglob("*.md"):
                rel_path = path.relative_to(g_dir).as_posix()
                try:
                    text = path.read_text(encoding="utf-8")
                    for line_idx, line in enumerate(text.splitlines(), start=1):
                        if query_lower in line.lower():
                            matches.append({
                                "file": rel_path,
                                "line": line_idx,
                                "content": line.strip(),
                            })
                            if len(matches) >= 20:
                                return matches
                except Exception:
                    continue
            return matches

        return await loop.run_in_executor(None, _do_search)

    # ---------------------------------------------------------
    # Machine Structured Data (Tasks and Config)
    # ---------------------------------------------------------

    async def save_task(self, task: AgentTask) -> None:
        filepath = self.guild_dir(task.guild_id) / "tasks" / f"{task.task_id}.json"
        content = json.dumps(task.to_dict(), indent=2)
        async with self._get_lock(f"task_{task.guild_id}_{task.task_id}"):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_text, filepath, content)

    async def get_task(self, task_id: str) -> AgentTask | None:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._find_task, task_id)

    def _find_task(self, task_id: str) -> AgentTask | None:
        if not self.base_dir.exists():
            return None
        for g_dir in self.base_dir.iterdir():
            if g_dir.is_dir():
                t_path = g_dir / "tasks" / f"{task_id}.json"
                if t_path.exists():
                    try:
                        data = json.loads(t_path.read_text(encoding="utf-8"))
                        return AgentTask.from_dict(data)
                    except Exception:
                        return None
        return None

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        """Convenience method returning parsed POLICY.md and SERVER.md settings."""
        policy_text = await self.read_doc(guild_id, "POLICY.md")
        mod_policy: dict[str, Any] = {}
        for line in policy_text.splitlines():
            if ":" in line and line.strip().startswith("-"):
                parts = line.strip().lstrip("-").split(":", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                mod_policy[k] = {"enabled": True, "action": v}
        return {"moderation_policy": mod_policy}

    async def save_config(self, guild_id: int, config: dict[str, Any]) -> None:
        lines = ["# POLICY.md — Moderation & Governance Policies\n"]
        for k, v in config.get("moderation_policy", {}).items():
            action = v.get("action", "warn") if isinstance(v, dict) else v
            lines.append(f"- {k}: {action}")
        await self.write_doc(guild_id, "POLICY.md", "\n".join(lines) + "\n")
