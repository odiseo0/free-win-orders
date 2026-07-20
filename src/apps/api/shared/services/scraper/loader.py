from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Sequence

from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from src.apps.api.shared.db.base import Base, Date


class CardListing(MappedAsDataclass, Base, Date, kw_only=True):
    __table_args__ = (
        UniqueConstraint("code", "condition", name="uq_card_listings_code_condition"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        init=False,
        autoincrement=True,
        primary_key=True,
    )
    name: Mapped[str]
    set: Mapped[str]
    code: Mapped[str]
    price: Mapped[Decimal]
    rarity: Mapped[str]
    condition: Mapped[str]
    stock: Mapped[int] = mapped_column(default=0)


@dataclass(slots=True)
class ScraperLoadResult:
    card_listings_loaded: int = 0


class ScraperDataStore(Protocol):
    async def upsert_card_listings(self, rows: Sequence[dict[str, object]]) -> int: ...


class CardListingData(Protocol):
    name: str
    set: str
    code: str
    price: str
    rarity: str
    condition: str
    stock: int


def _parse_price(price: str) -> Decimal:
    if price == "N/A":
        return Decimal("0")

    return Decimal(price.replace("$", "").replace(",", "").strip())


def _card_listing_row(listing: CardListingData) -> dict[str, object]:
    return {
        "name": listing.name,
        "set": listing.set,
        "code": listing.code,
        "price": _parse_price(listing.price),
        "rarity": listing.rarity,
        "condition": listing.condition,
        "stock": listing.stock,
    }


class SQLAlchemyScraperStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_card_listings(self, rows: Sequence[dict[str, object]]) -> int:
        if not rows:
            return 0

        stmt = postgresql_insert(CardListing).values(list(rows))
        stmt = stmt.on_conflict_do_update(
            constraint="uq_card_listings_code_condition",
            set_={
                "name": stmt.excluded.name,
                "set": stmt.excluded.set,
                "price": stmt.excluded.price,
                "rarity": stmt.excluded.rarity,
                "stock": stmt.excluded.stock,
            },
        )

        await self.db.execute(stmt)
        await self.db.commit()

        return len(rows)


async def load_scraped_data(
    store: ScraperDataStore,
    *,
    card_listings: Sequence[CardListingData] = (),
) -> ScraperLoadResult:
    card_rows = [_card_listing_row(listing) for listing in card_listings]

    card_listings_loaded = 0

    if card_rows:
        card_listings_loaded = await store.upsert_card_listings(card_rows)

    return ScraperLoadResult(card_listings_loaded=card_listings_loaded)


async def load_scraped_data_to_database(
    db: AsyncSession,
    *,
    card_listings: Sequence[CardListingData] = (),
) -> ScraperLoadResult:
    return await load_scraped_data(
        SQLAlchemyScraperStore(db), card_listings=card_listings
    )
