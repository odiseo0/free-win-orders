from typing import Protocol

from src.apps.api.members.domain.entities import Member


class MemberRepository(Protocol):
    async def list(self) -> list[Member]: ...
