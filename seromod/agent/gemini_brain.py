from __future__ import annotations

import json
import logging
from typing import Any

from seromod.agent.brain import Brain, BrainMessage
from seromod.agent.decisions import (
    AgentDecision,
    DecisionAction,
    ModerationAnalysisResult,
    ModerationEvidence,
    ToolCallRequest,
)
from seromod.tools.base import ToolSchema

log = logging.getLogger("seromod.brain.gemini")


class GeminiBrain(Brain):
    """Gemini implementation of the Brain interface."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._configured = False

    def _ensure_client(self):
        if not self._configured:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
            self._configured = True

    async def think(
        self,
        messages: list[BrainMessage],
        tools: list[ToolSchema],
        system_prompt: str,
    ) -> AgentDecision:
        self._ensure_client()

        # Format prompt describing tools and instructions for structured response
        tools_desc = []
        for t in tools:
            tools_desc.append({
                "tool": t.name,
                "description": t.description,
                "parameters": t.parameters,
            })

        user_content_parts = [
            system_prompt,
            f"\nAVAILABLE TOOLS:\n{json.dumps(tools_desc, indent=2)}",
            "\nCONVERSATION HISTORY:",
        ]

        for m in messages:
            user_content_parts.append(f"[{m.role.upper()}]: {m.content}")

        user_content_parts.append(
            """
RESPOND IN RAW JSON with either a tool call decision or final response:
Format 1 (Tool Call):
{
  "action": "tool_call",
  "reasoning": "Explain reason here",
  "tool_calls": [
    {"tool": "tool_name", "arguments": {"param": "value"}}
  ]
}

Format 2 (Final Response):
{
  "action": "respond",
  "response": "Your response to the user"
}
"""
        )

        prompt = "\n".join(user_content_parts)
        response = await self._model.generate_content_async(prompt)
        text = response.text or ""

        # Parse JSON
        try:
            # Clean possible markdown blocks
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            data = json.loads(clean_text.strip())
            action_str = data.get("action", "respond")
            if action_str == "tool_call":
                tcs = [
                    ToolCallRequest(tool=tc["tool"], arguments=tc.get("arguments", {}))
                    for tc in data.get("tool_calls", [])
                ]
                return AgentDecision(
                    action=DecisionAction.TOOL_CALL,
                    tool_calls=tcs,
                    reasoning=data.get("reasoning", ""),
                )
            else:
                return AgentDecision(
                    action=DecisionAction.RESPOND,
                    response=data.get("response", text),
                )
        except Exception as e:
            log.warning("Could not parse JSON from Gemini response: %s", e)
            return AgentDecision(action=DecisionAction.RESPOND, response=text)

    async def analyze_moderation(
        self,
        content: str,
        context_messages: list[str],
        policy_instructions: str,
    ) -> ModerationAnalysisResult:
        self._ensure_client()
        prompt = f"""You are a Discord moderation analysis engine.
{policy_instructions}

MESSAGE TO EVALUATE: "{content}"
RECENT CONTEXT: {json.dumps(context_messages)}

Analyze context and respond strictly in JSON:
{{
  "classification": "profanity|harassment|spam|none",
  "confidence": 0.0 to 1.0,
  "severity": 1 to 5,
  "action": "allow|warn|timeout|kick|ban|escalate",
  "reason": "Brief explanation",
  "evidence": [
    {{"message_id": "current", "snippet": "matched text", "flagged_terms": ["term"]}}
  ]
}}
"""
        response = await self._model.generate_content_async(prompt)
        text = response.text or ""

        try:
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            data = json.loads(clean_text.strip())

            ev = [
                ModerationEvidence(
                    message_id=e.get("message_id", "current"),
                    snippet=e.get("snippet", ""),
                    flagged_terms=e.get("flagged_terms", []),
                )
                for e in data.get("evidence", [])
            ]

            return ModerationAnalysisResult(
                classification=data.get("classification", "none"),
                confidence=float(data.get("confidence", 0.9)),
                severity=int(data.get("severity", 1)),
                action=data.get("action", "allow"),
                reason=data.get("reason", "Analyzed by AI"),
                evidence=ev,
            )
        except Exception as e:
            log.warning("Failed to parse moderation JSON: %s", e)
            return ModerationAnalysisResult(
                classification="none",
                confidence=0.5,
                severity=1,
                action="allow",
                reason=f"Parse fallback: {e}",
            )
