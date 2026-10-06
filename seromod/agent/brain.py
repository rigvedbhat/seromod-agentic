from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from seromod.agent.decisions import AgentDecision, DecisionAction, ModerationAnalysisResult, ToolCallRequest
from seromod.tools.base import ToolSchema


@dataclass
class BrainMessage:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)


class Brain(ABC):
    """Provider-independent Brain interface.

    The model proposes decisions/tool-calls through structured objects.
    It never touches the Discord API directly.
    """

    @abstractmethod
    async def think(
        self,
        messages: list[BrainMessage],
        tools: list[ToolSchema],
        system_prompt: str,
    ) -> AgentDecision:
        """Returns structured AgentDecision."""
        ...

    @abstractmethod
    async def analyze_moderation(
        self,
        content: str,
        context_messages: list[str],
        policy_instructions: str,
    ) -> ModerationAnalysisResult:
        """Evaluates message moderation returning structured ModerationAnalysisResult."""
        ...
