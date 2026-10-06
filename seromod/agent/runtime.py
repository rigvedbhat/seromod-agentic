from __future__ import annotations

import asyncio
import logging
from typing import Any

from seromod.agent.brain import Brain, BrainMessage
from seromod.agent.context import ServerContext, build_server_context
from seromod.agent.decisions import DecisionAction
from seromod.agent.task import AgentTask, PendingApproval, TaskStatus
from seromod.guild_handle import GuildHandle, MemberInfo
from seromod.memory.decisions import DecisionRecord
from seromod.memory.workspace import WorkspaceMemoryStore
from seromod.policy.engine import PolicyEngine
from seromod.skills.base import Skill
from seromod.tools.registry import ToolRegistry

log = logging.getLogger("seromod.runtime")


class AgentRuntime:
    """The central Agent Runtime loop.

    Governs observe -> reason -> act -> verify -> reflect cycle.
    Integrates with per-guild WorkspaceMemoryStore for human-readable markdown memory.
    """

    def __init__(
        self,
        brain: Brain,
        tools: ToolRegistry,
        memory: WorkspaceMemoryStore,
        policy: PolicyEngine,
    ):
        self.brain = brain
        self.tools = tools
        self.memory = memory
        self.policy = policy
        self._guild_locks: dict[int, asyncio.Lock] = {}

    def get_guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._guild_locks:
            self._guild_locks[guild_id] = asyncio.Lock()
        return self._guild_locks[guild_id]

    async def execute_task(
        self,
        task: AgentTask,
        guild: GuildHandle,
        skill: Skill,
        user_message: str,
        caller: MemberInfo | None = None,
    ) -> AgentTask:
        """Runs the multi-step agent loop with concurrency protection."""
        guild_lock = self.get_guild_lock(guild.guild_id)

        async with guild_lock:
            task.status = TaskStatus.RUNNING
            await self.memory.save_task(task)

            # Available tools from skill
            active_tools = skill.get_tools(self.tools)
            tool_schemas = [t.schema() for t in active_tools]
            tools_map = {t.name: t for t in active_tools}

            messages: list[BrainMessage] = [
                BrainMessage(role="user", content=user_message),
            ]

            while True:
                # 1. OBSERVE: Fetch fresh context (authoritative live Discord + workspace memory docs)
                context: ServerContext = await build_server_context(guild, self.memory)
                system_prompt = skill.system_prompt(context)

                # Check budget limits before thinking
                if task.is_limit_exceeded():
                    task.status = TaskStatus.BUDGET_EXCEEDED
                    task.result_message = "Task stopped: iteration or tool call limit exceeded."
                    await self.memory.save_task(task)
                    return task

                task.record_step()

                # 2. REASON: Brain evaluates state & messages
                decision = await self.brain.think(messages, tool_schemas, system_prompt)

                # Handle immediate finish or conversational response
                if decision.action in (DecisionAction.FINISH, DecisionAction.RESPOND):
                    task.status = TaskStatus.COMPLETED
                    task.result_message = decision.response or "Task completed successfully."
                    await self.memory.save_task(task)
                    return task

                if decision.action == DecisionAction.ASK_USER:
                    task.status = TaskStatus.WAITING_FOR_USER
                    task.result_message = decision.response or "Waiting for user clarification."
                    await self.memory.save_task(task)
                    return task

                if decision.action == DecisionAction.TOOL_CALL:
                    if not decision.tool_calls:
                        task.status = TaskStatus.COMPLETED
                        task.result_message = decision.response or "Done."
                        await self.memory.save_task(task)
                        return task

                    # 3. ACT & VERIFY: Process tool calls safely
                    has_failure = False
                    for call_req in decision.tool_calls:
                        tool_obj = tools_map.get(call_req.tool)
                        if not tool_obj:
                            err_msg = f"Tool '{call_req.tool}' is not available in skill '{skill.name}'."
                            task.record_tool_call(call_req.tool, call_req.arguments, success=False, error=err_msg)
                            messages.append(BrainMessage(role="tool", content=f"Error: {err_msg}", tool_call_id=call_req.call_id))
                            has_failure = True
                            continue

                        # A. Schema validation
                        valid, val_err = tool_obj.validate_args(call_req.arguments)
                        if not valid:
                            task.record_tool_call(call_req.tool, call_req.arguments, success=False, error=val_err)
                            messages.append(BrainMessage(role="tool", content=f"Validation Error: {val_err}", tool_call_id=call_req.call_id))
                            has_failure = True
                            continue

                        # B. Policy & permission check
                        pol_eval = self.policy.evaluate_tool_execution(tool_obj, call_req.arguments, caller=caller)
                        if not pol_eval.allowed:
                            task.record_tool_call(call_req.tool, call_req.arguments, success=False, error=pol_eval.reason)
                            messages.append(BrainMessage(role="tool", content=f"Policy Denied: {pol_eval.reason}", tool_call_id=call_req.call_id))
                            has_failure = True
                            continue

                        # C. High impact check -> WAITING_FOR_APPROVAL
                        if pol_eval.requires_approval:
                            task.status = TaskStatus.WAITING_FOR_APPROVAL
                            task.pending_approval = PendingApproval(
                                tool=call_req.tool,
                                arguments=call_req.arguments,
                                reason=pol_eval.reason,
                            )
                            task.result_message = f"Action requires approval: {pol_eval.reason}"
                            await self.memory.save_task(task)
                            return task

                        # D. Execute Tool against Live Discord or Workspace
                        try:
                            result = await tool_obj.execute(guild, call_req.arguments)
                        except Exception as e:
                            result = None
                            err_str = f"Execution exception: {e}"

                        if result and result.success:
                            task.record_tool_call(call_req.tool, call_req.arguments, success=True, result_data=result.data)

                            # Record audit decision in DECISIONS.md if this altered server structure
                            if any(w in call_req.tool for w in ("create", "delete", "edit", "timeout", "kick", "ban")):
                                entity_type = "channel" if "channel" in call_req.tool else ("category" if "category" in call_req.tool else "role")
                                entity_name = call_req.arguments.get("name") or call_req.arguments.get("channel_name") or "unknown"
                                await self.memory.record_decision(
                                    guild.guild_id,
                                    DecisionRecord(
                                        guild_id=guild.guild_id,
                                        entity_type=entity_type,
                                        action=call_req.tool,
                                        entity_name=entity_name,
                                        reason=f"Executed by Seromod task {task.task_id}: {task.goal}",
                                        requested_by=task.created_by,
                                        task_id=task.task_id,
                                        metadata={"args": call_req.arguments, "result": result.data},
                                    ),
                                )

                            messages.append(BrainMessage(role="tool", content=f"Success: {result.data}", tool_call_id=call_req.call_id))
                        else:
                            err = result.error if result else err_str
                            task.record_tool_call(call_req.tool, call_req.arguments, success=False, error=err)
                            messages.append(BrainMessage(role="tool", content=f"Error: {err}", tool_call_id=call_req.call_id))
                            has_failure = True

                    # 4. PARTIALLY_COMPLETED Resilience Check
                    if has_failure and task.completed_actions:
                        task.status = TaskStatus.PARTIALLY_COMPLETED
                        await self.memory.save_task(task)

                    await self.memory.save_task(task)

    async def approve_and_continue(
        self,
        task: AgentTask,
        guild: GuildHandle,
        skill: Skill,
        approver_id: int,
    ) -> AgentTask:
        """Resumes a task that was paused in WAITING_FOR_APPROVAL."""
        if task.status != TaskStatus.WAITING_FOR_APPROVAL or not task.pending_approval:
            raise ValueError(f"Task {task.task_id} is not in WAITING_FOR_APPROVAL state.")

        pending = task.pending_approval
        pending.approved_by = approver_id
        tool_obj = self.tools.get(pending.tool)
        if not tool_obj:
            task.status = TaskStatus.FAILED
            task.result_message = f"Pending tool '{pending.tool}' no longer exists."
            await self.memory.save_task(task)
            return task

        # Execute approved tool
        res = await tool_obj.execute(guild, pending.arguments)
        task.record_tool_call(pending.tool, pending.arguments, success=res.success, result_data=res.data, error=res.error)
        task.pending_approval = None

        if res.success:
            task.status = TaskStatus.COMPLETED
            task.result_message = f"Approved action '{pending.tool}' executed successfully."
            # Record in DECISIONS.md
            await self.memory.record_decision(
                guild.guild_id,
                DecisionRecord(
                    guild_id=guild.guild_id,
                    entity_type="channel" if "channel" in pending.tool else "action",
                    action=pending.tool,
                    entity_name=pending.arguments.get("name") or pending.arguments.get("channel_name") or "target",
                    reason=f"Approved by {approver_id}: {pending.reason}",
                    requested_by=approver_id,
                    task_id=task.task_id,
                ),
            )
        else:
            task.status = TaskStatus.PARTIALLY_COMPLETED if task.completed_actions else TaskStatus.FAILED
            task.result_message = f"Approved action '{pending.tool}' failed: {res.error}"

        await self.memory.save_task(task)
        return task
