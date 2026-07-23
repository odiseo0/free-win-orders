from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.api.cards.application import card_listing_cases
from src.api.cards.domain import CardListingListResponse, CardListingResponse
from src.core import Ok
from src.core.services.cache import InMemoryCache
from src.core.services.scraper.transformers import CardListing


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class EmptyListingDAO:
    def __init__(self) -> None:
        self.searches = 0

    async def search_by_name(
        self,
        db: object,
        query: str,
        *,
        limit: int,
    ) -> list[object]:
        self.searches += 1
        return []


class FakeScraper:
    def __init__(self) -> None:
        self.searches = 0

    async def search(self, query: str) -> list[CardListing]:
        self.searches += 1
        return [
            CardListing(
                name=query,
                set="Legend of Blue Eyes White Dragon",
                code="LOB-001",
                price="$19.99",
                rarity="Ultra Rare",
                condition="Near Mint",
                stock=2,
            )
        ]


class PersistedListingDAO:
    async def search_by_name(
        self,
        db: object,
        query: str,
        *,
        limit: int,
    ) -> list[object]:
        return [
            SimpleNamespace(
                id=7,
                card_id=3,
                ygo_id=89631139,
                ygo_set="Legend of Blue Eyes White Dragon",
                name=query,
                code="LOB-001",
                price=Decimal("18.50"),
                rarity="Ultra Rare",
                condition="Played",
                stock=1,
                date_added=None,
                date_updated=None,
            )
        ]


class PaginatedListingDAO:
    def __init__(self) -> None:
        self.reads = 0

    async def get_multi(self, db: object, **kwargs: object) -> tuple[list[object], int]:
        self.reads += 1
        return (
            [
                CardListingResponse(
                    id=7,
                    card_id=3,
                    ygo_id=89631139,
                    ygo_set="Legend of Blue Eyes White Dragon",
                    name="Blue-Eyes White Dragon",
                    code="LOB-001",
                    price=Decimal("18.50"),
                    rarity="Ultra Rare",
                    condition="Played",
                    stock=1,
                )
            ],
            12,
        )


@pytest.mark.anyio
async def test_search_uses_scraper_after_cache_and_database_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dao = EmptyListingDAO()
    scraper = FakeScraper()
    cache = InMemoryCache()
    monkeypatch.setattr(card_listing_cases, "dao", dao)

    result = await card_listing_cases.search(
        object(),
        cache,
        scraper,
        "Blue-Eyes White Dragon",
    )

    assert result == Ok(
        [
            CardListingResponse(
                ygo_set="Legend of Blue Eyes White Dragon",
                name="Blue-Eyes White Dragon",
                code="LOB-001",
                price=Decimal("19.99"),
                rarity="Ultra Rare",
                condition="Near Mint",
                stock=2,
            )
        ]
    )
    assert dao.searches == 1
    assert scraper.searches == 1


@pytest.mark.anyio
async def test_search_returns_cached_scraped_results_without_new_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dao = EmptyListingDAO()
    scraper = FakeScraper()
    cache = InMemoryCache()
    monkeypatch.setattr(card_listing_cases, "dao", dao)

    first_result = await card_listing_cases.search(
        object(), cache, scraper, "Dark Magician"
    )
    second_result = await card_listing_cases.search(
        object(), cache, scraper, "  dark   magician  "
    )

    assert second_result == first_result
    assert dao.searches == 1
    assert scraper.searches == 1


@pytest.mark.anyio
async def test_search_prefers_database_results_over_scraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = FakeScraper()
    monkeypatch.setattr(card_listing_cases, "dao", PersistedListingDAO())

    result = await card_listing_cases.search(
        object(),
        InMemoryCache(),
        scraper,
        "Blue-Eyes White Dragon",
    )

    assert isinstance(result, Ok)
    assert result.value[0].id == 7
    assert result.value[0].price == Decimal("18.50")
    assert scraper.searches == 0


@pytest.mark.anyio
async def test_listings_cache_items_and_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dao = PaginatedListingDAO()
    cache = InMemoryCache()
    monkeypatch.setattr(card_listing_cases, "dao", dao)

    first = await card_listing_cases.get_multi(
        object(), cache, page=2, shows=10
    )
    second = await card_listing_cases.get_multi(
        object(), cache, page=2, shows=10
    )

    assert isinstance(first, Ok)
    assert first.value == CardListingListResponse(
        items=first.value.items,
        total=12,
    )
    assert second == first
    assert dao.reads == 1
