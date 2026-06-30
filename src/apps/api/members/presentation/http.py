from litestar import Controller, Router, get

from src.apps.api.members.application.dto import ListMembersQuery
from src.apps.api.members.application.use_cases import ListMembersUseCase
from src.apps.api.members.infrastructure.repository import InMemoryMemberRepository


class MembersController(Controller):
    path = "/members"

    @get()
    async def list_members(self) -> list[dict[str, str]]:
        use_case = ListMembersUseCase(repository=InMemoryMemberRepository())
        members = await use_case.execute(ListMembersQuery())
        return [{"id": member.id, "name": member.name} for member in members]


members_router = Router(path="", route_handlers=[MembersController])
