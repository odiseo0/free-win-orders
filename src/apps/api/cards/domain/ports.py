from typing import Protocol

from src.apps.api.cards.domain.entities import Card


class CardRepository(Protocol):
    async def search(self, query: str) -> list[Card]: ...
