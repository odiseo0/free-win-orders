from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from src.api.order_requests.repository import (
    CardListingReferenceDAO,
    CardListingSnapshot,
)
from src.api.order_requests.repository.card_listings import card_listings
from src.core.db import Base
from src.core.utils.utils import Empty


class MappingResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row

    def mappings(self) -> MappingResult:
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self.row


class RecordingDB:
    def __init__(self, row: dict[str, object] | None) -> None:
        self.row = row
        self.statements: list[object] = []

    async def execute(self, statement: object) -> MappingResult:
        self.statements.append(statement)
        return MappingResult(self.row)


def _sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_external_listing_projection_is_registered_in_shared_metadata() -> None:
    assert card_listings.metadata is Base.metadata
    assert card_listings.info["schema_owner"] == "free-win-search"


@pytest.mark.anyio
async def test_get_snapshot_reads_only_the_order_snapshot_columns() -> None:
    db = RecordingDB(
        {
            "id": 5,
            "name": "Blue-Eyes White Dragon",
            "ygo_set": "Legend of Blue Eyes White Dragon",
            "code": "LOB-001",
            "price": Decimal("8.50"),
            "rarity": "Ultra Rare",
            "condition": "Near Mint",
        }
    )

    result = await CardListingReferenceDAO().get_snapshot(db, 5)

    assert result == CardListingSnapshot(
        id=5,
        name="Blue-Eyes White Dragon",
        ygo_set="Legend of Blue Eyes White Dragon",
        code="LOB-001",
        price=Decimal("8.50"),
        rarity="Ultra Rare",
        condition="Near Mint",
    )
    statement = _sql(db.statements[0])
    assert "FROM card_listings" in statement
    assert "card_listings.id = 5" in statement
    assert "card_listings.stock" not in statement
    assert "card_listings.card_id" not in statement


@pytest.mark.anyio
async def test_get_snapshot_returns_empty_for_an_unknown_listing() -> None:
    db = RecordingDB(None)

    result = await CardListingReferenceDAO().get_snapshot(db, 404)

    assert result is Empty
