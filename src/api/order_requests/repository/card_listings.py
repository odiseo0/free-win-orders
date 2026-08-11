from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, Numeric, String, Table, select

from src.core.db import Base
from src.core.utils.utils import Empty, EmptyType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


card_listings = Table(
    "card_listings",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("ygo_set", String, nullable=False),
    Column("code", String, nullable=False),
    Column("price", Numeric, nullable=False),
    Column("rarity", String, nullable=False),
    Column("condition", String, nullable=False),
    extend_existing=True,
    info={"schema_owner": "free-win-search"},
)


@dataclass(frozen=True, slots=True)
class CardListingSnapshot:
    id: int
    name: str
    ygo_set: str
    code: str
    price: Decimal
    rarity: str
    condition: str


class CardListingReferenceDAO:
    async def get_snapshot(
        self,
        db: AsyncSession,
        card_listing_id: int,
    ) -> CardListingSnapshot | EmptyType:
        statement = select(
            card_listings.c.id,
            card_listings.c.name,
            card_listings.c.ygo_set,
            card_listings.c.code,
            card_listings.c.price,
            card_listings.c.rarity,
            card_listings.c.condition,
        ).where(card_listings.c.id == card_listing_id)
        row = (await db.execute(statement)).mappings().one_or_none()

        if row is None:
            return Empty

        return CardListingSnapshot(
            id=row["id"],
            name=row["name"],
            ygo_set=row["ygo_set"],
            code=row["code"],
            price=row["price"],
            rarity=row["rarity"],
            condition=row["condition"],
        )


dao_card_listing_references = CardListingReferenceDAO()
