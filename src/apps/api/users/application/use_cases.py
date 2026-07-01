from src.apps.api.members.application.dto import ListMembersQuery
from src.apps.api.members.domain.entities import Member
from src.apps.api.members.domain.ports import MemberRepository


class ListMembersUseCase:
    def __init__(self, repository: MemberRepository) -> None:
        self.repository = repository

    async def execute(self, _: ListMembersQuery) -> list[Member]:
        return await self.repository.list()
