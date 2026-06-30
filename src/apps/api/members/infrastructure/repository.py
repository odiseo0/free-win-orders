from src.apps.api.members.domain.entities import Member


class InMemoryMemberRepository:
    async def list(self) -> list[Member]:
        return [Member(id="demo-member", name="Admin")]
