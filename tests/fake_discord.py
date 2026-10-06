from __future__ import annotations

import time
from typing import Any

from seromod.guild_handle import (
    CategoryInfo,
    ChannelInfo,
    ChannelType,
    GuildHandle,
    MemberInfo,
    MessageInfo,
    RoleInfo,
)


class FakeGuild(GuildHandle):
    """In-memory test implementation of GuildHandle representing live Discord state."""

    def __init__(self, guild_id: int = 123456, name: str = "Test Server"):
        self.guild_id = guild_id
        self.name = name
        self._categories: list[CategoryInfo] = []
        self._channels: list[ChannelInfo] = []
        self._roles: list[RoleInfo] = [RoleInfo(id=1, name="@everyone", is_default=True)]
        self._members: dict[int, MemberInfo] = {}
        self._messages: list[MessageInfo] = []
        self._timed_out: dict[int, int] = {}
        self._kicked: list[int] = []
        self._banned: list[int] = []
        self._next_id = 100

    async def get_channels(self) -> list[ChannelInfo]:
        return list(self._channels)

    async def get_categories(self) -> list[CategoryInfo]:
        return list(self._categories)

    async def get_roles(self) -> list[RoleInfo]:
        return list(self._roles)

    async def get_member(self, user_id: int) -> MemberInfo | None:
        return self._members.get(user_id)

    def add_member(self, member: MemberInfo) -> None:
        self._members[member.id] = member

    async def create_category(self, name: str) -> CategoryInfo:
        self._next_id += 1
        cat = CategoryInfo(id=self._next_id, name=name, position=len(self._categories))
        self._categories.append(cat)
        return cat

    async def create_text_channel(
        self,
        name: str,
        *,
        category_id: int | None = None,
        topic: str | None = None,
    ) -> ChannelInfo:
        self._next_id += 1
        ch = ChannelInfo(
            id=self._next_id,
            name=name,
            channel_type=ChannelType.TEXT,
            category_id=category_id,
            topic=topic,
            position=len(self._channels),
        )
        self._channels.append(ch)
        return ch

    async def create_voice_channel(
        self,
        name: str,
        *,
        category_id: int | None = None,
    ) -> ChannelInfo:
        self._next_id += 1
        ch = ChannelInfo(
            id=self._next_id,
            name=name,
            channel_type=ChannelType.VOICE,
            category_id=category_id,
            position=len(self._channels),
        )
        self._channels.append(ch)
        return ch

    async def create_role(self, name: str) -> RoleInfo:
        self._next_id += 1
        role = RoleInfo(id=self._next_id, name=name, position=len(self._roles))
        self._roles.append(role)
        return role

    async def edit_channel(
        self,
        channel_id: int,
        *,
        name: str | None = None,
        category_id: int | None = None,
        topic: str | None = None,
    ) -> ChannelInfo:
        for idx, ch in enumerate(self._channels):
            if ch.id == channel_id:
                new_ch = ChannelInfo(
                    id=ch.id,
                    name=name if name is not None else ch.name,
                    channel_type=ch.channel_type,
                    category_id=category_id if category_id is not None else ch.category_id,
                    topic=topic if topic is not None else ch.topic,
                    position=ch.position,
                )
                self._channels[idx] = new_ch
                return new_ch
        raise ValueError(f"Channel {channel_id} not found")

    async def delete_channel(self, channel_id: int) -> None:
        self._channels = [c for c in self._channels if c.id != channel_id]

    async def edit_category(self, category_id: int, *, name: str) -> CategoryInfo:
        for idx, cat in enumerate(self._categories):
            if cat.id == category_id:
                new_cat = CategoryInfo(id=cat.id, name=name, position=cat.position)
                self._categories[idx] = new_cat
                return new_cat
        raise ValueError(f"Category {category_id} not found")

    async def delete_category(self, category_id: int) -> None:
        self._categories = [c for c in self._categories if c.id != category_id]

    async def edit_role(self, role_id: int, *, name: str) -> RoleInfo:
        for idx, r in enumerate(self._roles):
            if r.id == role_id:
                new_r = RoleInfo(id=r.id, name=name, position=r.position)
                self._roles[idx] = new_r
                return new_r
        raise ValueError(f"Role {role_id} not found")

    async def delete_role(self, role_id: int) -> None:
        self._roles = [r for r in self._roles if r.id != role_id]

    async def send_message(self, channel_id: int, content: str) -> MessageInfo:
        self._next_id += 1
        msg = MessageInfo(
            id=self._next_id,
            channel_id=channel_id,
            author_id=999,
            content=content,
            timestamp=time.time(),
        )
        self._messages.append(msg)
        return msg

    async def timeout_member(self, user_id: int, duration_seconds: int, reason: str) -> None:
        self._timed_out[user_id] = duration_seconds

    async def kick_member(self, user_id: int, reason: str) -> None:
        self._kicked.append(user_id)

    async def ban_member(self, user_id: int, reason: str) -> None:
        self._banned.append(user_id)
