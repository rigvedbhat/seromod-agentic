from __future__ import annotations

from seromod.agent.brain import Brain, BrainMessage
from seromod.agent.decisions import (
    AgentDecision,
    DecisionAction,
    ModerationAnalysisResult,
    ToolCallRequest,
)
from seromod.tools.base import ToolSchema


class FakeBrain(Brain):
    """Deterministic FakeBrain returning predetermined AgentDecisions."""

    def __init__(self, decisions: list[AgentDecision] | None = None):
        self.decisions: list[AgentDecision] = list(decisions or [])
        self.call_history: list[list[BrainMessage]] = []
        self.default_moderation_result = ModerationAnalysisResult(
            classification="none",
            confidence=1.0,
            severity=1,
            action="allow",
            reason="Clean message",
        )

    def queue_decision(self, decision: AgentDecision) -> None:
        self.decisions.append(decision)

    async def think(
        self,
        messages: list[BrainMessage],
        tools: list[ToolSchema],
        system_prompt: str,
    ) -> AgentDecision:
        self.call_history.append(messages)
        if self.decisions:
            return self.decisions.pop(0)

        # Default fallback: complete task
        return AgentDecision(
            action=DecisionAction.FINISH,
            response="FakeBrain finished thinking.",
        )

    async def analyze_moderation(
        self,
        content: str,
        context_messages: list[str],
        policy_instructions: str,
    ) -> ModerationAnalysisResult:
        if self.decisions:
            # If a decision is queued that matches moderation, we could return it
            pass
        return self.default_moderation_result
