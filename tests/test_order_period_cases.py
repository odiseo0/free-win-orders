from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.api.order_periods.application import order_period_cases
from src.api.order_periods.domain import entities as order_period_entities
from src.api.order_periods.domain import (
    OrderPeriodAlreadyClosed,
    OrderPeriodCannotCloseDraft,
    OrderPeriodCreate,
    OrderPeriodDateConflict,
    OrderPeriodEventType,
    OrderPeriodImmutableField,
    OrderPeriodNotFound,
    OrderPeriodResponse,
    OrderPeriodStatus,
    OrderPeriodUpdate,
)
from src.api.roles.domain import Actor, PermissionCode, USER_PERMISSIONS
from src.core import Err, Ok
from src.core.db import DAOError
from src.core.utils.utils import Empty


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
USER = Actor(user_id=2, permissions=USER_PERMISSIONS)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakePeriod:
    id: int = 7
    name: str = "Pedido agosto 2026"
    opens_at: datetime = NOW + timedelta(days=1)
    closes_at: datetime = NOW + timedelta(days=15)
    created_by_user_id: int = ADMIN.user_id
    date_added: datetime = NOW
    date_updated: datetime | None = None


@dataclass
class FakeHistory:
    id: int
    order_period_id: int
    event: OrderPeriodEventType
    actor_user_id: int
    occurred_at: datetime
    changes: list[dict[str, object]] = field(default_factory=list)


class FakeDB:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class RecordingHistoryDAO:
    def __init__(self, *, fail: bool = False) -> None:
        self.created: list[dict[str, object]] = []
        self.fail = fail

    async def create(self, db: object, **values: object) -> FakeHistory:
        if self.fail:
            raise DAOError
        self.created.append(values)
        return FakeHistory(id=len(self.created), **values)  # type: ignore[arg-type]

    async def get_for_period(
        self, db: object, order_period_id: int, *, page: int, shows: int
    ) -> list[FakeHistory]:
        records = [
            FakeHistory(
                id=index,
                order_period_id=order_period_id,
                event=OrderPeriodEventType.UPDATED,
                actor_user_id=ADMIN.user_id,
                occurred_at=NOW + timedelta(minutes=index),
            )
            for index in range(1, 4)
        ]
        return list(reversed(records))[page : page + shows]


class RecordingPeriodDAO:
    def __init__(
        self,
        period: FakePeriod | object = Empty,
        *,
        fail_create: bool = False,
    ) -> None:
        self.period = period
        self.fail_create = fail_create
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.locked_ids: list[int] = []
        self.list_arguments: dict[str, object] | None = None

    async def create(self, db: object, **values: object) -> FakePeriod:
        if self.fail_create:
            raise DAOError
        self.created.append(values)
        self.period = FakePeriod(**values)
        return self.period

    async def get(self, db: object, order_period_id: int) -> FakePeriod | object:
        return self.period

    async def get_for_update(
        self, db: object, order_period_id: int
    ) -> FakePeriod | object:
        self.locked_ids.append(order_period_id)
        return self.period

    async def update(
        self, db: object, period: FakePeriod, values: dict[str, object]
    ) -> FakePeriod:
        self.updated.append(values)
        for key, value in values.items():
            setattr(period, key, value)
        period.date_updated = NOW
        return period

    async def get_multi(self, db: object, **kwargs: object) -> tuple[list[FakePeriod], int]:
        self.list_arguments = kwargs
        periods = [
            FakePeriod(id=1, date_added=NOW - timedelta(days=2)),
            FakePeriod(id=2, date_added=NOW - timedelta(days=1)),
            FakePeriod(id=3, date_added=NOW),
        ]
        page = int(kwargs["page"])
        shows = int(kwargs["shows"])
        return list(reversed(periods))[page : page + shows], len(periods)


def install_daos(
    monkeypatch: pytest.MonkeyPatch,
    period_dao: RecordingPeriodDAO,
    history_dao: RecordingHistoryDAO,
) -> None:
    monkeypatch.setattr(order_period_cases, "dao", period_dao)
    monkeypatch.setattr(order_period_cases, "history_dao", history_dao)
    monkeypatch.setattr(order_period_cases, "datetime_now", lambda: NOW)
    monkeypatch.setattr(order_period_entities, "datetime_now", lambda: NOW)


@pytest.mark.anyio
async def test_create_persists_period_and_history_in_one_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao = RecordingPeriodDAO()
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    contract = OrderPeriodCreate(
        name="Pedido agosto 2026",
        opens_at=NOW + timedelta(days=1),
        closes_at=NOW + timedelta(days=15),
    )

    result = await order_period_cases.create(db, ADMIN, contract)

    assert isinstance(result, Ok)
    assert (
        OrderPeriodResponse.model_validate(result.value).status
        is OrderPeriodStatus.DRAFT
    )
    assert period_dao.created[0]["created_by_user_id"] == ADMIN.user_id
    assert history_dao.created == [
        {
            "order_period_id": 7,
            "event": OrderPeriodEventType.CREATED,
            "actor_user_id": ADMIN.user_id,
            "occurred_at": NOW,
            "changes": [],
        }
    ]
    assert db.commits == 1
    assert db.rollbacks == 0


@pytest.mark.anyio
async def test_create_allows_duplicate_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao = RecordingPeriodDAO()
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    contract = OrderPeriodCreate(
        name="Pedido repetido",
        opens_at=NOW,
        closes_at=NOW + timedelta(days=1),
    )

    first = await order_period_cases.create(db, ADMIN, contract)
    second = await order_period_cases.create(db, ADMIN, contract)

    assert isinstance(first, Ok)
    assert isinstance(second, Ok)
    assert len(period_dao.created) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("closes_at", [NOW, NOW - timedelta(microseconds=1)])
async def test_create_rejects_a_period_without_a_future_close(
    monkeypatch: pytest.MonkeyPatch, closes_at: datetime
) -> None:
    period_dao = RecordingPeriodDAO()
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    contract = OrderPeriodCreate(
        name="Pedido vencido",
        opens_at=NOW - timedelta(days=1),
        closes_at=closes_at,
    )

    result = await order_period_cases.create(db, ADMIN, contract)

    assert result == Err(OrderPeriodDateConflict())
    assert period_dao.created == []
    assert history_dao.created == []
    assert db.commits == 0


@pytest.mark.anyio
@pytest.mark.parametrize("failure_at", ["period", "history"])
async def test_create_rolls_back_repository_failures(
    monkeypatch: pytest.MonkeyPatch, failure_at: str
) -> None:
    period_dao = RecordingPeriodDAO(fail_create=failure_at == "period")
    history_dao = RecordingHistoryDAO(fail=failure_at == "history")
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    contract = OrderPeriodCreate(
        name="Pedido agosto",
        opens_at=NOW,
        closes_at=NOW + timedelta(days=1),
    )

    with pytest.raises(DAOError):
        await order_period_cases.create(db, ADMIN, contract)

    assert db.rollbacks == 1
    assert db.commits == 0


@pytest.mark.anyio
async def test_get_one_translates_repository_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, RecordingPeriodDAO(), RecordingHistoryDAO())

    result = await order_period_cases.get_one(object(), 404)

    assert result == Err(OrderPeriodNotFound(404))


@pytest.mark.anyio
async def test_list_coordinates_visibility_filter_pagination_and_ordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao = RecordingPeriodDAO()
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    result = await order_period_cases.get_multi(
        object(),
        USER,
        page=2,
        shows=1,
        status=OrderPeriodStatus.OPEN,
    )

    assert isinstance(result, Ok)
    periods, total = result.value
    assert [period.id for period in periods] == [2]
    assert total == 3
    assert period_dao.list_arguments == {
        "page": 1,
        "shows": 1,
        "status": OrderPeriodStatus.OPEN,
        "now": NOW,
        "include_drafts": False,
        "ordering": [("date_added", True)],
    }


@pytest.mark.anyio
async def test_admin_list_can_include_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    period_dao = RecordingPeriodDAO()
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    await order_period_cases.get_multi(
        object(), ADMIN, page=1, shows=100, status=OrderPeriodStatus.DRAFT
    )

    assert period_dao.list_arguments is not None
    assert period_dao.list_arguments["include_drafts"] is True


@pytest.mark.anyio
async def test_update_draft_records_only_effective_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod()
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    new_closing = period.closes_at + timedelta(days=7)

    result = await order_period_cases.update(
        db,
        ADMIN,
        period.id,
        OrderPeriodUpdate(name=period.name, closes_at=new_closing),
    )

    assert isinstance(result, Ok)
    assert period_dao.locked_ids == [period.id]
    assert period_dao.updated == [{"closes_at": new_closing}]
    assert history_dao.created[0]["event"] is OrderPeriodEventType.UPDATED
    assert history_dao.created[0]["changes"] == [
        {
            "field": "closesAt",
            "oldValue": (NOW + timedelta(days=15)).isoformat(),
            "newValue": new_closing.isoformat(),
        }
    ]
    assert db.commits == 1


@pytest.mark.anyio
async def test_update_without_effective_changes_writes_no_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod()
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)

    result = await order_period_cases.update(
        db, ADMIN, period.id, OrderPeriodUpdate(name=period.name)
    )

    assert isinstance(result, Ok)
    assert period_dao.updated == []
    assert history_dao.created == []
    assert db.commits == 0


@pytest.mark.anyio
async def test_update_draft_can_change_name_and_both_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod()
    original_opening = period.opens_at
    original_closing = period.closes_at
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    new_opening = NOW + timedelta(days=2)
    new_closing = NOW + timedelta(days=20)

    result = await order_period_cases.update(
        db,
        ADMIN,
        period.id,
        OrderPeriodUpdate(
            name="Pedido septiembre 2026",
            opens_at=new_opening,
            closes_at=new_closing,
        ),
    )

    assert isinstance(result, Ok)
    assert period_dao.updated == [
        {
            "name": "Pedido septiembre 2026",
            "opens_at": new_opening,
            "closes_at": new_closing,
        }
    ]
    assert history_dao.created[0]["changes"] == [
        {
            "field": "name",
            "oldValue": "Pedido agosto 2026",
            "newValue": "Pedido septiembre 2026",
        },
        {
            "field": "opensAt",
            "oldValue": original_opening.isoformat(),
            "newValue": new_opening.isoformat(),
        },
        {
            "field": "closesAt",
            "oldValue": original_closing.isoformat(),
            "newValue": new_closing.isoformat(),
        },
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["name", "opens_at"])
async def test_update_open_period_rejects_immutable_fields(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    period = FakePeriod(opens_at=NOW - timedelta(days=1))
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    install_daos(monkeypatch, period_dao, history_dao)
    value: Any = "Otro nombre" if field == "name" else NOW + timedelta(days=1)

    result = await order_period_cases.update(
        FakeDB(), ADMIN, period.id, OrderPeriodUpdate(**{field: value})
    )

    assert result == Err(OrderPeriodImmutableField(field))
    assert period_dao.updated == []
    assert history_dao.created == []


@pytest.mark.anyio
@pytest.mark.parametrize("new_closing", [NOW, NOW - timedelta(microseconds=1)])
async def test_update_open_period_rejects_non_future_close(
    monkeypatch: pytest.MonkeyPatch, new_closing: datetime
) -> None:
    period = FakePeriod(opens_at=NOW - timedelta(days=1))
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    install_daos(monkeypatch, period_dao, history_dao)

    result = await order_period_cases.update(
        FakeDB(), ADMIN, period.id, OrderPeriodUpdate(closes_at=new_closing)
    )

    assert result == Err(OrderPeriodDateConflict())
    assert period_dao.updated == []
    assert history_dao.created == []


@pytest.mark.anyio
@pytest.mark.parametrize("delta", [timedelta(days=-7), timedelta(days=7)])
async def test_update_open_period_can_shorten_or_extend_future_close(
    monkeypatch: pytest.MonkeyPatch, delta: timedelta
) -> None:
    period = FakePeriod(
        opens_at=NOW - timedelta(days=1), closes_at=NOW + timedelta(days=14)
    )
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)
    new_closing = period.closes_at + delta

    result = await order_period_cases.update(
        db, ADMIN, period.id, OrderPeriodUpdate(closes_at=new_closing)
    )

    assert isinstance(result, Ok)
    assert result.value.closes_at == new_closing
    assert db.commits == 1


@pytest.mark.anyio
async def test_update_revalidates_a_period_that_expired_before_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod(
        opens_at=NOW - timedelta(days=2),
        closes_at=NOW,
    )
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    install_daos(monkeypatch, period_dao, history_dao)

    result = await order_period_cases.update(
        FakeDB(),
        ADMIN,
        period.id,
        OrderPeriodUpdate(closes_at=NOW + timedelta(days=7)),
    )

    assert result == Err(OrderPeriodAlreadyClosed(period.id))
    assert period_dao.locked_ids == [period.id]
    assert period_dao.updated == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "update",
    [
        OrderPeriodUpdate(name="No reabrir"),
        OrderPeriodUpdate(opens_at=NOW + timedelta(days=1)),
        OrderPeriodUpdate(closes_at=NOW + timedelta(days=7)),
    ],
)
async def test_update_closed_period_rejects_every_change(
    monkeypatch: pytest.MonkeyPatch, update: OrderPeriodUpdate
) -> None:
    period = FakePeriod(
        opens_at=NOW - timedelta(days=2), closes_at=NOW - timedelta(days=1)
    )
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    install_daos(monkeypatch, period_dao, history_dao)

    result = await order_period_cases.update(FakeDB(), ADMIN, period.id, update)

    assert result == Err(OrderPeriodAlreadyClosed(period.id))
    assert period_dao.updated == []
    assert history_dao.created == []


@pytest.mark.anyio
async def test_update_missing_period_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao = RecordingPeriodDAO()
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    result = await order_period_cases.update(
        FakeDB(), ADMIN, 404, OrderPeriodUpdate(name="No existe")
    )

    assert result == Err(OrderPeriodNotFound(404))
    assert period_dao.locked_ids == [404]


@pytest.mark.anyio
async def test_close_open_period_sets_close_to_now_and_records_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod(opens_at=NOW - timedelta(days=1))
    original_closing = period.closes_at
    period_dao = RecordingPeriodDAO(period)
    history_dao = RecordingHistoryDAO()
    db = FakeDB()
    install_daos(monkeypatch, period_dao, history_dao)

    result = await order_period_cases.close(db, ADMIN, period.id)

    assert isinstance(result, Ok)
    assert (
        OrderPeriodResponse.model_validate(result.value).status
        is OrderPeriodStatus.CLOSED
    )
    assert period_dao.updated == [{"closes_at": NOW}]
    assert history_dao.created[0] == {
        "order_period_id": period.id,
        "event": OrderPeriodEventType.CLOSED_EARLY,
        "actor_user_id": ADMIN.user_id,
        "occurred_at": NOW,
        "changes": [
            {
                "field": "closesAt",
                "oldValue": original_closing.isoformat(),
                "newValue": NOW.isoformat(),
            }
        ],
    }
    assert db.commits == 1


@pytest.mark.anyio
async def test_close_draft_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    period = FakePeriod()
    period_dao = RecordingPeriodDAO(period)
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    result = await order_period_cases.close(FakeDB(), ADMIN, period.id)

    assert result == Err(OrderPeriodCannotCloseDraft(period.id))
    assert period_dao.updated == []


@pytest.mark.anyio
async def test_close_closed_period_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    period = FakePeriod(
        opens_at=NOW - timedelta(days=2), closes_at=NOW - timedelta(days=1)
    )
    period_dao = RecordingPeriodDAO(period)
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    result = await order_period_cases.close(FakeDB(), ADMIN, period.id)

    assert result == Err(OrderPeriodAlreadyClosed(period.id))
    assert period_dao.updated == []


@pytest.mark.anyio
async def test_close_missing_period_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao = RecordingPeriodDAO()
    install_daos(monkeypatch, period_dao, RecordingHistoryDAO())

    result = await order_period_cases.close(FakeDB(), ADMIN, 404)

    assert result == Err(OrderPeriodNotFound(404))
    assert period_dao.locked_ids == [404]


@pytest.mark.anyio
async def test_history_is_returned_newest_first_and_paginated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = FakePeriod()
    install_daos(
        monkeypatch, RecordingPeriodDAO(period), RecordingHistoryDAO()
    )

    result = await order_period_cases.get_history(
        object(), period.id, page=1, shows=2
    )

    assert isinstance(result, Ok)
    assert [entry.id for entry in result.value] == [3, 2]


@pytest.mark.anyio
async def test_history_missing_period_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, RecordingPeriodDAO(), RecordingHistoryDAO())

    result = await order_period_cases.get_history(object(), 404, page=1, shows=10)

    assert result == Err(OrderPeriodNotFound(404))
