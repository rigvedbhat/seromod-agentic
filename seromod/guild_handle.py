from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ChannelType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    CATEGORY = "category"


@dataclass(frozen=True)
class RoleInfo:
    id: int
    name: str
    permissions: int = 0
    position: int = 0
    managed: bool = False
    is_default: bool = False  # @everyone


@dataclass(frozen=True)
class CategoryInfo:
    id: int
    name: str
    position: int = 0


@dataclass(frozen=True)
class ChannelInfo:
    id: int
    name: str
    channel_type: ChannelType
    category_id: int | None = None
    topic: str | None = None
    position: int = 0


@dataclass(frozen=True)
class MemberInfo:
    id: int
    name: str
    display_name: str
    role_ids: list[int] = field(default_factory=list)
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False


@dataclass(frozen=True)
class MessageInfo:
    id: int
    channel_id: int
    author_id: int
    content: str
    timestamp: float


@runtime_checkable
class GuildHandle(Protocol):
    """Protocol representing a live Discord Guild.

    Discord live state is always the authoritative source of truth.
    Local memory only holds derived facts, logs, and preferences.
    """

    guild_id: int
    name: str

    async def get_channels(self) -> list[ChannelInfo]: ...
    async def get_categories(self) -> list[CategoryInfo]: ...
    async def get_roles(self) -> list[RoleInfo]: ...
    async def get_member(self, user_id: int) -> MemberInfo | None: ...

    async def create_text_channel(
        self,
        name: str,
        *,
        category_id: int | None = None,
        topic: str | None = None,
    ) -> ChannelInfo: ...

    async def create_voice_channel(
        self,
        name: str,
        *,
        category_id: int | None = None,
    ) -> ChannelInfo: ...

    async def create_category(self, name: str) -> CategoryInfo: ...

    async def create_role(self, name: str) -> RoleInfo: ...

    async def edit_channel(
        self,
        channel_id: int,
        *,
        name: str | None = None,
        category_id: int | None = None,
        topic: str | None = None,
    ) -> ChannelInfo: ...

    async def delete_channel(self, channel_id: int) -> None: ...

    async def edit_category(self, category_id: int, *, name: str) -> CategoryInfo: ...

    async def delete_category(self, category_id: int) -> None: ...

    async def edit_role(self, role_id: int, *, name: str) -> RoleInfo: ...

    async def delete_role(self, role_id: int) -> None: ...

    async def send_message(self, channel_id: int, content: str) -> MessageInfo: ...

    async def timeout_member(
        self,
        user_id: int,
        duration_seconds: int,
        reason: str,
    ) -> None: ...

    async def kick_member(self, user_id: int, reason: str) -> None: ...

    async def ban_member(self, user_id: int, reason: str) -> None: ...
