class CoolstuffScraperService:
    async def search_cards(self, query: str) -> list[dict[str, str]]:
        return [{"source": "coolstuffinc", "query": query}]
