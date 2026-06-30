class YgoProApiService:
    async def search_cards(self, query: str) -> list[dict[str, str]]:
        return [{"source": "ygoprodeck", "query": query}]
