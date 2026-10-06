from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DecisionRecord:
    record_id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:10]}")
    guild_id: int = 0
    entity_type: str = ""  # "channel", "role", "category", "moderation", "policy"
    action: str = ""       # "create", "edit", "delete", "warn", "timeout", "kick", "ban"
    entity_name: str = ""
    reason: str = ""
    requested_by: int | None = None
    task_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionRecord:
        return cls(**data)
