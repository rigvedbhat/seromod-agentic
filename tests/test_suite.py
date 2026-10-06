from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from seromod.agent.decisions import (
    AgentDecision,
    DecisionAction,
    ModerationAnalysisResult,
    ModerationEvidence,
    ToolCallRequest,
)
from seromod.agent.runtime import AgentRuntime
from seromod.agent.task import AgentTask, TaskStatus
from seromod.guild_handle import MemberInfo, MessageInfo
from seromod.memory.decisions import DecisionRecord
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.policy.engine import PolicyEngine
from seromod.skills.conversation import ConversationSkill
from seromod.skills.moderation import ModerationSkill
from seromod.skills.server_builder import ServerBuilderSkill
from seromod.tools.categories import CreateCategoryTool, GetCategoriesTool
from seromod.tools.channels import CreateChannelTool, DeleteChannelTool, GetChannelsTool
from seromod.tools.members import TimeoutMemberTool
from seromod.tools.memory_tools import SearchDecisionsTool
from seromod.tools.registry import ToolRegistry
from seromod.tools.roles import CreateRoleTool, GetRolesTool
from seromod.tools.server import GetServerStateTool
from tests.fake_brain import FakeBrain
from tests.fake_discord import FakeGuild


class TestSeromodAgent(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceMemoryStore(base_dir=Path(self.temp_dir) / "workspace" / "guilds")
        self.policy_engine = PolicyEngine()
        self.fake_guild = FakeGuild(guild_id=98765, name="Minecraft SMP Server")

        self.registry = ToolRegistry()
        self.registry.register(GetChannelsTool())
        self.registry.register(CreateChannelTool())
        self.registry.register(DeleteChannelTool())
        self.registry.register(GetCategoriesTool())
        self.registry.register(CreateCategoryTool())
        self.registry.register(GetRolesTool())
        self.registry.register(CreateRoleTool())
        self.registry.register(GetServerStateTool())
        self.registry.register(TimeoutMemberTool())
        self.registry.register(SearchDecisionsTool(self.workspace))

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_agent_runtime_server_build_loop(self):
        """Test full multi-step server building loop using FakeBrain and FakeGuild."""
        fake_brain = FakeBrain()

        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="create_category", arguments={"name": "Minecraft SMP"}),
                ],
                reasoning="Create primary category",
            )
        )

        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="create_channel", arguments={"name": "smp-rules", "category_name": "Minecraft SMP"}),
                    ToolCallRequest(tool="create_channel", arguments={"name": "server-chat", "category_name": "Minecraft SMP"}),
                ],
                reasoning="Create SMP channels",
            )
        )

        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.FINISH,
                response="Server build completed.",
            )
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(
            task_type="server_build",
            goal="Build Minecraft SMP structure",
            guild_id=self.fake_guild.guild_id,
        )

        result_task = await runtime.execute_task(
            task=task,
            guild=self.fake_guild,
            skill=ServerBuilderSkill(),
            user_message="Build this server for a Minecraft SMP.",
        )

        self.assertEqual(result_task.status, TaskStatus.COMPLETED)

        categories = await self.fake_guild.get_categories()
        channels = await self.fake_guild.get_channels()

        self.assertTrue(any(c.name == "Minecraft SMP" for c in categories))
        self.assertTrue(any(ch.name == "smp-rules" for ch in channels))
        self.assertTrue(any(ch.name == "server-chat" for ch in channels))

        decisions = await self.workspace.get_decisions(self.fake_guild.guild_id)
        self.assertGreaterEqual(len(decisions), 3)

    async def test_waiting_for_approval_and_resumption(self):
        """Test high-impact actions triggering WAITING_FOR_APPROVAL and persisting pending approval."""
        await self.fake_guild.create_text_channel("old-channel")

        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="delete_channel", arguments={"channel_name": "old-channel"}),
                ],
                reasoning="Clean up old channel",
            )
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(
            task_type="server_edit",
            goal="Clean up old channel",
            guild_id=self.fake_guild.guild_id,
        )

        result_task = await runtime.execute_task(
            task=task,
            guild=self.fake_guild,
            skill=ServerBuilderSkill(),
            user_message="Delete old-channel",
        )

        self.assertEqual(result_task.status, TaskStatus.WAITING_FOR_APPROVAL)
        self.assertIsNotNone(result_task.pending_approval)
        self.assertEqual(result_task.pending_approval.tool, "delete_channel")

        live_channels = await self.fake_guild.get_channels()
        self.assertTrue(any(ch.name == "old-channel" for ch in live_channels))

        resumed = await runtime.approve_and_continue(
            task=result_task,
            guild=self.fake_guild,
            skill=ServerBuilderSkill(),
            approver_id=999,
        )

        self.assertEqual(resumed.status, TaskStatus.COMPLETED)
        live_channels_after = await self.fake_guild.get_channels()
        self.assertFalse(any(ch.name == "old-channel" for ch in live_channels_after))

    async def test_partially_completed_resilience(self):
        """Test partial failure records PARTIALLY_COMPLETED and stores completed/failed actions."""
        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="create_channel", arguments={"name": "welcome"}),
                    ToolCallRequest(tool="missing_tool", arguments={}),
                ],
                reasoning="Partial action test",
            )
        )
        fake_brain.queue_decision(
            AgentDecision(action=DecisionAction.FINISH, response="Stop"),
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(
            task_type="server_build",
            goal="Partial build",
            guild_id=self.fake_guild.guild_id,
        )

        result_task = await runtime.execute_task(
            task=task,
            guild=self.fake_guild,
            skill=ServerBuilderSkill(),
            user_message="Run partial test",
        )

        self.assertEqual(len(result_task.completed_actions), 1)
        self.assertEqual(len(result_task.failed_actions), 1)
        self.assertEqual(result_task.completed_actions[0]["args"]["name"], "welcome")

    async def test_conversation_answers_why_did_you_create(self):
        """Test agent answers 'Why did you create X?' using memory."""
        await self.workspace.record_decision(
            self.fake_guild.guild_id,
            DecisionRecord(
                guild_id=self.fake_guild.guild_id,
                entity_type="channel",
                action="create_channel",
                entity_name="clips-and-highlights",
                reason="Dedicated place for members to share gameplay clips",
                requested_by=1001,
                task_id="task_123",
            ),
        )

        fake_brain = FakeBrain()
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.TOOL_CALL,
                tool_calls=[
                    ToolCallRequest(tool="search_decisions", arguments={"entity_name": "clips-and-highlights"}),
                ],
            )
        )
        fake_brain.queue_decision(
            AgentDecision(
                action=DecisionAction.RESPOND,
                response="I created #clips-and-highlights as a dedicated place for members to share gameplay clips.",
            )
        )

        runtime = AgentRuntime(fake_brain, self.registry, self.workspace, self.policy_engine)
        task = AgentTask(task_type="conversation", goal="Explain creation", guild_id=self.fake_guild.guild_id)

        result_task = await runtime.execute_task(
            task=task,
            guild=self.fake_guild,
            skill=ConversationSkill(),
            user_message="Why did you create #clips-and-highlights?",
        )

        self.assertEqual(result_task.status, TaskStatus.COMPLETED)
        self.assertIn("gameplay clips", result_task.result_message or "")

    async def test_moderation_pipeline_evaluation(self):
        """Test event-driven moderation filtering and execution."""
        fake_brain = FakeBrain()
        fake_brain.default_moderation_result = ModerationAnalysisResult(
            classification="spam",
            confidence=0.92,
            severity=3,
            action="timeout",
            reason="Repeated promotional badword",
            evidence=[ModerationEvidence(message_id=99, snippet="badword promo", flagged_terms=["badword"])],
        )

        mod_skill = ModerationSkill(fake_brain, self.registry, self.workspace, self.policy_engine)
        user = MemberInfo(id=777, name="Bob", display_name="Bob")
        msg = MessageInfo(id=99, channel_id=1, author_id=777, content="Check out this badword deal!", timestamp=10.0)

        res = await mod_skill.handle_message_event(msg, user, self.fake_guild)
        self.assertEqual(res["status"], "processed")
        self.assertEqual(res["action_taken"], "timeout")
        self.assertEqual(self.fake_guild._timed_out.get(777), 60)


if __name__ == "__main__":
    unittest.main()
