from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionAction(str, Enum):
    TOOL_CALL = "tool_call"
    RESPOND = "respond"
    ASK_USER = "ask_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    FINISH = "finish"


@dataclass
class ToolCallRequest:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class AgentDecision:
    """Decision produced by the Brain/Agent for the next step."""

    action: DecisionAction
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    response: str | None = None
    reasoning: str = ""
    confidence: float = 1.0
    pending_approval_details: dict[str, Any] | None = None


@dataclass
class ModerationEvidence:
    message_id: int | str
    snippet: str
    flagged_terms: list[str] = field(default_factory=list)


@dataclass
class ModerationAnalysisResult:
    """Structured, detailed moderation evaluation returned by Brain/Analysis."""

    classification: str  # e.g. "harassment", "profanity", "spam", "none"
    confidence: float  # 0.0 to 1.0
    severity: int  # 1 (low) to 5 (critical)
    action: str  # "allow", "warn", "timeout", "kick", "ban", "escalate"
    reason: str
    evidence: list[ModerationEvidence] = field(default_factory=list)
