from __future__ import annotations

from abc import ABC, abstractmethod

from seromod.agent.context import ServerContext
from seromod.tools.base import Tool
from seromod.tools.registry import ToolRegistry


class Skill(ABC):
    """A Skill is a configuration bundle that specializes the runtime for specific tasks."""

    name: str
    description: str

    @abstractmethod
    def system_prompt(self, context: ServerContext) -> str: ...

    @abstractmethod
    def get_tools(self, registry: ToolRegistry) -> list[Tool]: ...
