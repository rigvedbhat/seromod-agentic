from __future__ import annotations

import asyncio
from typing import Any

from seromod.agent.brain import Brain, BrainMessage
from seromod.agent.context import ServerContext, build_server_context
from seromod.agent.decisions import ModerationAnalysisResult
from seromod.guild_handle import GuildHandle, MemberInfo, MessageInfo
from seromod.memory.decisions import DecisionRecord
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.policy.engine import PolicyEngine
from seromod.tools.registry import ToolRegistry


class ModerationSkill:
    name = "moderation"
    description = "Event-driven context-aware message moderation with deterministic policy enforcement and workspace audit recording."

    def __init__(
        self,
        brain: Brain,
        tools: ToolRegistry,
        workspace: WorkspaceMemoryStore,
        policy: PolicyEngine,
    ):
        self.brain = brain
        self.tools = tools
        self.workspace = workspace
        self.policy = policy
        self._profanity_keywords = {"badword", "curseword", "hateword", "slur"}

    def fast_filter(self, content: str) -> bool:
        lower = content.lower()
        for kw in self._profanity_keywords:
            if kw in lower:
                return True
        if len(content) > 20 and sum(1 for c in content if c.isupper()) / len(content) > 0.8:
            return True
        return False

    async def handle_message_event(
        self,
        message: MessageInfo,
        author: MemberInfo,
        guild: GuildHandle,
        recent_channel_messages: list[str] | None = None,
    ) -> dict[str, Any]:
        if author.is_admin or author.is_owner:
            return {"status": "ignored", "reason": "User is admin/owner."}

        if not self.fast_filter(message.content):
            return {"status": "ignored", "reason": "Passed fast deterministic filter."}

        recent = recent_channel_messages or [message.content]
        config = await self.workspace.get_config(guild.guild_id)
        mod_policy = config.get("moderation_policy", {
            "profanity": {"enabled": True, "action": "warn"},
            "harassment": {"enabled": True, "action": "warn"},
            "spam": {"enabled": True, "action": "timeout"},
        })

        policy_instructions = f"Current server moderation policy from POLICY.md: {mod_policy}"

        analysis: ModerationAnalysisResult = await self.brain.analyze_moderation(
            content=message.content,
            context_messages=recent,
            policy_instructions=policy_instructions,
        )

        pol_result = self.policy.evaluate_moderation(analysis, mod_policy)

        action_taken = "none"
        if not pol_result.allowed:
            action_taken = "ignored_by_policy"
        elif pol_result.requires_approval or analysis.action == "escalate":
            action_taken = "escalated"
            await self.workspace.record_decision(
                guild.guild_id,
                DecisionRecord(
                    guild_id=guild.guild_id,
                    entity_type="moderation",
                    action="escalate",
                    entity_name=f"user_{author.id}",
                    reason=f"Escalated violation ({analysis.classification}): {analysis.reason}",
                    requested_by=None,
                    metadata={"analysis": analysis.__dict__},
                ),
            )
        else:
            action_taken = analysis.action
            if analysis.action == "timeout":
                t_tool = self.tools.get("timeout_member")
                if t_tool:
                    await t_tool.execute(guild, {"user_id": author.id, "duration_seconds": 60, "reason": analysis.reason})

            await self.workspace.record_decision(
                guild.guild_id,
                DecisionRecord(
                    guild_id=guild.guild_id,
                    entity_type="moderation",
                    action=analysis.action,
                    entity_name=f"user_{author.id}",
                    reason=f"Automod {analysis.action} for {analysis.classification}: {analysis.reason}",
                    requested_by=None,
                    metadata={"analysis": analysis.__dict__},
                ),
            )

        return {
            "status": "processed",
            "action_taken": action_taken,
            "classification": analysis.classification,
            "confidence": analysis.confidence,
            "severity": analysis.severity,
            "reason": analysis.reason,
            "evidence": [e.__dict__ for e in analysis.evidence],
        }
