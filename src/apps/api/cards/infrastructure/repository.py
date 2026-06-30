from src.apps.api.cards.domain.entities import Card


class InMemoryCardRepository:
    async def search(self, query: str) -> list[Card]:
        if not query:
            return []
        return [Card(id="demo-card", name=query, quantity=1)]
