from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from src.api.order_requests.domain import OrderRequestEventType, OrderRequestStatus
from src.api.order_requests.repository import (
    OrderRequestDAO,
    OrderRequestHistoryDAO,
    OrderRequestItemDAO,
)
from src.core.db import DAOIntegrityError


def _sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class FakeResult:
    def __init__(self, *, values: list[object] | None = None, scalar: object = None):
        self.values = values or []
        self.scalar = scalar

    def unique(self) -> FakeResult:
        return self

    def scalars(self) -> FakeResult:
        return self

    def all(self) -> list[object]:
        return self.values

    def scalar_one_or_none(self) -> object:
        return self.scalar

    def scalar_one(self) -> object:
        return self.scalar


class RecordingDB:
    def __init__(self, *results: FakeResult):
        self.results = list(results)
        self.statements: list[object] = []
        self.added: list[object] = []
        self.flushes = 0

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1


class FailingFlushDB(RecordingDB):
    async def flush(self) -> None:
        raise IntegrityError("INSERT", {}, Exception("constraint"))


@pytest.mark.anyio
async def test_get_for_update_locks_the_request_row() -> None:
    expected = object()
    db = RecordingDB(FakeResult(scalar=expected))

    result = await OrderRequestDAO().get_for_update(db, 17)

    statement = _sql(db.statements[0])
    assert result is expected
    assert "order_requests.id = 17" in statement
    assert "FOR UPDATE" in statement


@pytest.mark.anyio
async def test_get_multi_filters_owner_period_and_status() -> None:
    expected = [object(), object()]
    db = RecordingDB(
        FakeResult(scalar=2),
        FakeResult(values=expected),
    )

    result, total = await OrderRequestDAO().get_multi(
        db,
        page=20,
        shows=10,
        owner_user_id=8,
        order_period_id=4,
        status=OrderRequestStatus.IN_REVIEW,
    )

    count_statement = _sql(db.statements[0])
    data_statement = _sql(db.statements[1])
    assert result == expected
    assert total == 2
    assert "created_by_user_id = 8" in count_statement
    assert "order_period_id = 4" in count_statement
    assert "status = 'in_review'" in count_statement
    assert "ORDER BY order_requests.date_added DESC" in data_statement
    assert "LIMIT 10 OFFSET 20" in data_statement


@pytest.mark.anyio
async def test_history_is_returned_newest_first() -> None:
    expected = [object()]
    db = RecordingDB(FakeResult(values=expected))

    result = await OrderRequestHistoryDAO().get_for_request(
        db,
        order_request_id=17,
        page=0,
        shows=25,
    )

    statement = _sql(db.statements[0])
    assert result == expected
    assert "order_request_id = 17" in statement
    assert "occurred_at DESC" in statement
    assert "LIMIT 25 OFFSET 0" in statement


@dataclass
class FakeListing:
    id: int = 5
    name: str = "Blue-Eyes White Dragon"
    ygo_set: str = "Legend of Blue Eyes White Dragon"
    code: str = "LOB-001"
    rarity: str = "Ultra Rare"
    condition: str = "Near Mint"
    price: Decimal = Decimal("8.505")


@pytest.mark.anyio
async def test_create_item_copies_listing_snapshot_and_initial_quantity() -> None:
    db = RecordingDB()

    item = await OrderRequestItemDAO().create_from_listing(
        db,
        order_request_id=17,
        listing=FakeListing(),
        requested_quantity=3,
    )

    assert item.card_listing_id == 5
    assert item.card_name == "Blue-Eyes White Dragon"
    assert item.card_set == "Legend of Blue Eyes White Dragon"
    assert item.estimated_unit_price == Decimal("8.51")
    assert item.requested_quantity == 3
    assert item.agreed_quantity == 3
    assert db.added == [item]
    assert db.flushes == 1


@pytest.mark.anyio
async def test_dao_creations_flush_without_committing() -> None:
    db = RecordingDB()
    request = await OrderRequestDAO().create(
        db,
        order_period_id=4,
        created_by_user_id=8,
        note="Buscar primera edición",
    )
    history = await OrderRequestHistoryDAO().create(
        db,
        order_request_id=17,
        event=OrderRequestEventType.CREATED,
        actor_user_id=8,
        changes=[],
    )

    assert request.status == OrderRequestStatus.SUBMITTED
    assert history.event == OrderRequestEventType.CREATED
    assert db.added == [request, history]
    assert db.flushes == 2


@pytest.mark.anyio
async def test_create_translates_integrity_errors_without_rolling_back() -> None:
    db = FailingFlushDB()

    with pytest.raises(DAOIntegrityError):
        await OrderRequestDAO().create(
            db,
            order_period_id=4,
            created_by_user_id=8,
            note=None,
        )


@pytest.mark.anyio
async def test_mutation_flushes_are_transaction_neutral() -> None:
    db = RecordingDB()

    await OrderRequestDAO().flush(db)

    assert db.flushes == 1
