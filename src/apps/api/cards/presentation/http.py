from litestar import Controller, Router, get

from src.apps.api.cards.application.dto import SearchCardsQuery
from src.apps.api.cards.application.use_cases import SearchCardsUseCase
from src.apps.api.cards.infrastructure.repository import InMemoryCardRepository


class CardsController(Controller):
    path = "/cards"

    @get("/search")
    async def search(self, q: str = "") -> list[dict[str, str | int]]:
        use_case = SearchCardsUseCase(repository=InMemoryCardRepository())
        cards = await use_case.execute(SearchCardsQuery(term=q))
        return [{"id": card.id, "name": card.name, "quantity": card.quantity} for card in cards]


cards_router = Router(path="", route_handlers=[CardsController])
