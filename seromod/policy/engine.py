from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from seromod.agent.decisions import ModerationAnalysisResult
from seromod.guild_handle import MemberInfo
from seromod.tools.base import Tool


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""
    override_action: str | None = None


class PolicyEngine:
    """Deterministic policy engine that governs what tools and actions can actually execute."""

    def evaluate_tool_execution(
        self,
        tool: Tool,
        args: dict[str, Any],
        caller: MemberInfo | None = None,
    ) -> PolicyEvaluationResult:
        # Check permissions if caller is known
        if caller is not None:
            if tool.requires_permission == "administrator" and not caller.is_admin and not caller.is_owner:
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Caller '{caller.name}' lacks Administrator permission.",
                )

        # Check high-impact approval
        if tool.high_impact:
            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=True,
                reason=f"Action '{tool.name}' is high-impact and requires explicit approval.",
            )

        return PolicyEvaluationResult(allowed=True, requires_approval=False)

    def evaluate_moderation(
        self,
        analysis: ModerationAnalysisResult,
        server_policy: dict[str, Any],
    ) -> PolicyEvaluationResult:
        """Determines whether a proposed moderation action is authorized by server configuration."""
        cat_config = server_policy.get(analysis.classification.lower(), {})
        if not cat_config.get("enabled", True):
            # Category disabled
            return PolicyEvaluationResult(
                allowed=False,
                reason=f"Moderation category '{analysis.classification}' is disabled in server policy.",
            )

        # High severity actions (kick/ban) always require approval unless policy specifically permits auto-ban
        if analysis.action in ("kick", "ban"):
            return PolicyEvaluationResult(
                allowed=True,
                requires_approval=True,
                reason=f"Moderation action '{analysis.action}' requires administrator approval.",
            )

        return PolicyEvaluationResult(allowed=True, requires_approval=False)
