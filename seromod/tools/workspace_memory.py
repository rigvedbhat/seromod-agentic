from __future__ import annotations

from typing import Any

from seromod.guild_handle import GuildHandle
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.tools.base import Tool, ToolResult


class MemoryReadTool(Tool):
    name = "memory_read"
    description = "Read the contents of a workspace memory file (e.g. 'SERVER.md', 'MEMORY.md', 'DECISIONS.md', 'POLICY.md', or 'memory/2026-10-03.md')."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The workspace file to read (e.g. 'SERVER.md', 'DECISIONS.md')"},
        },
        "required": ["filename"],
    }
    requires_permission = "view_channel"
    high_impact = False

    def __init__(self, workspace: WorkspaceMemoryStore):
        self.workspace = workspace

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        filename = args["filename"].strip()
        content = await self.workspace.read_doc(guild.guild_id, filename)
        if not content:
            return ToolResult(success=True, data={"filename": filename, "content": "(File is empty or does not exist)"})
        return ToolResult(success=True, data={"filename": filename, "content": content})


class MemoryWriteTool(Tool):
    name = "memory_write"
    description = "Write or append a note/fact to the guild agent workspace. For daily observations, write to today's daily log. For long-term facts, write to MEMORY.md."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The workspace file to write (e.g. 'MEMORY.md', 'SERVER.md')"},
            "content": {"type": "string", "description": "Content to write or append"},
            "append": {"type": "boolean", "default": True, "description": "Whether to append to the file or overwrite"},
        },
        "required": ["filename", "content"],
    }
    requires_permission = "manage_guild"
    high_impact = False

    def __init__(self, workspace: WorkspaceMemoryStore):
        self.workspace = workspace

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        filename = args["filename"].strip()
        content = args["content"].strip()
        append = args.get("append", True)

        if append:
            await self.workspace.append_doc(guild.guild_id, filename, f"\n{content}\n")
        else:
            await self.workspace.write_doc(guild.guild_id, filename, content)

        return ToolResult(success=True, data={"status": "written", "filename": filename, "appended": append})


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search across all workspace memory files for a keyword or topic (e.g. 'Minecraft', 'clips', 'admin preference')."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search term or topic to find in memory files"},
        },
        "required": ["query"],
    }
    requires_permission = "view_channel"
    high_impact = False

    def __init__(self, workspace: WorkspaceMemoryStore):
        self.workspace = workspace

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        query = args["query"].strip()
        results = await self.workspace.search_workspace(guild.guild_id, query)
        return ToolResult(success=True, data={"query": query, "matches": results})


class MemoryUpdateTool(Tool):
    name = "memory_update"
    description = "Update specific server facts or admin preferences in SERVER.md or policy rules in POLICY.md."
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": ["server_purpose", "admin_preference", "policy"], "description": "Target section to update"},
            "detail": {"type": "string", "description": "The new detail or policy rule to record"},
        },
        "required": ["target", "detail"],
    }
    requires_permission = "manage_guild"
    high_impact = False

    def __init__(self, workspace: WorkspaceMemoryStore):
        self.workspace = workspace

    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        target = args["target"]
        detail = args["detail"].strip()

        if target == "policy":
            await self.workspace.append_doc(guild.guild_id, "POLICY.md", f"- {detail}\n")
        elif target == "admin_preference":
            await self.workspace.append_doc(guild.guild_id, "SERVER.md", f"- Admin Preference: {detail}\n")
        else:
            await self.workspace.append_doc(guild.guild_id, "SERVER.md", f"- Purpose Note: {detail}\n")

        return ToolResult(success=True, data={"updated_target": target, "recorded": detail})
