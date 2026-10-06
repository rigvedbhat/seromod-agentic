from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class PendingApproval:
    tool: str
    arguments: dict[str, Any]
    reason: str
    requested_at: float = field(default_factory=time.time)
    approved_by: int | None = None


@dataclass
class AgentTask:
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:10]}")
    task_type: str = "general"  # "server_build", "server_edit", "conversation", "moderation"
    goal: str = ""
    guild_id: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_by: int | None = None

    # Limits
    max_iterations: int = 30
    max_tool_calls: int = 100
    timeout_seconds: int = 300

    # Tracking
    iterations_used: int = 0
    tool_calls_used: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # For multi-step tasks & resilience: completed actions, failed actions, and remaining plan
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    failed_actions: list[dict[str, Any]] = field(default_factory=list)
    remaining_plan: list[dict[str, Any]] = field(default_factory=list)

    # Pending high-impact approval state
    pending_approval: PendingApproval | None = None
    result_message: str | None = None

    def record_step(self) -> None:
        self.iterations_used += 1
        self.updated_at = time.time()

    def record_tool_call(self, tool: str, args: dict[str, Any], success: bool, result_data: Any = None, error: str | None = None) -> None:
        self.tool_calls_used += 1
        self.updated_at = time.time()
        record = {
            "tool": tool,
            "args": args,
            "success": success,
            "timestamp": time.time(),
        }
        if success:
            record["result"] = result_data
            self.completed_actions.append(record)
        else:
            record["error"] = error
            self.failed_actions.append(record)

    def is_limit_exceeded(self) -> bool:
        if self.iterations_used >= self.max_iterations:
            return True
        if self.tool_calls_used >= self.max_tool_calls:
            return True
        if (time.time() - self.created_at) > self.timeout_seconds:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTask:
        d = dict(data)
        d["status"] = TaskStatus(d.get("status", TaskStatus.PENDING.value))
        if d.get("pending_approval"):
            d["pending_approval"] = PendingApproval(**d["pending_approval"])
        return cls(**d)
