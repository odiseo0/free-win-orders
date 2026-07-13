import asyncio
from dataclasses import dataclass, field
from decimal import Decimal

from src.apps.api.shared.services.scraper.loader import load_scraped_data


@dataclass
class CardListing:
    name: str
    set: str
    code: str
    price: str
    rarity: str
    condition: str
    stock: int = 0


@dataclass
class FakeScraperStore:
    card_rows: list[dict[str, object]] = field(default_factory=list)

    async def upsert_card_listings(self, rows: list[dict[str, object]]) -> int:
        self.card_rows.extend(rows)
        return len(rows)


def test_load_scraped_data_normalizes_rows_before_writing() -> None:
    store = FakeScraperStore()

    result = asyncio.run(
        load_scraped_data(
            store,
            card_listings=[
                CardListing(
                    name="Blue-Eyes White Dragon - Legend of Blue Eyes White Dragon",
                    set="Legend of Blue Eyes White Dragon",
                    code="LOB-001",
                    price="$19.99",
                    rarity="Ultra Rare",
                    condition="Near Mint",
                    stock=2,
                )
            ],
        )
    )

    assert result.card_listings_loaded == 1
    assert store.card_rows == [
        {
            "name": "Blue-Eyes White Dragon - Legend of Blue Eyes White Dragon",
            "set": "Legend of Blue Eyes White Dragon",
            "code": "LOB-001",
            "price": Decimal("19.99"),
            "rarity": "Ultra Rare",
            "condition": "Near Mint",
            "stock": 2,
        }
    ]


def test_load_scraped_data_skips_empty_batches() -> None:
    store = FakeScraperStore()

    result = asyncio.run(load_scraped_data(store))

    assert result.card_listings_loaded == 0
    assert store.card_rows == []
