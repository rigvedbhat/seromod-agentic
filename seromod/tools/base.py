from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from seromod.guild_handle import GuildHandle


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]
    requires_permission: str = "send_messages"
    high_impact: bool = False


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]
    requires_permission: str = "send_messages"
    high_impact: bool = False

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            requires_permission=self.requires_permission,
            high_impact=self.high_impact,
        )

    def validate_args(self, args: dict[str, Any]) -> tuple[bool, str | None]:
        """Simple schema validator checking required fields."""
        required = self.parameters.get("required", [])
        for field_name in required:
            if field_name not in args:
                return False, f"Missing required parameter '{field_name}'"
        return True, None

    @abstractmethod
    async def execute(self, guild: GuildHandle, args: dict[str, Any]) -> ToolResult:
        """Executes the tool against the live Discord GuildHandle."""
        ...
