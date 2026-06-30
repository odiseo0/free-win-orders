from src.apps.api.cards.application.dto import SearchCardsQuery
from src.apps.api.cards.domain.entities import Card
from src.apps.api.cards.domain.ports import CardRepository


class SearchCardsUseCase:
    def __init__(self, repository: CardRepository) -> None:
        self.repository = repository

    async def execute(self, query: SearchCardsQuery) -> list[Card]:
        return await self.repository.search(query.term)
