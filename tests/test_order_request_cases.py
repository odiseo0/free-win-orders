from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.api.order_periods.domain import OrderPeriodNotFound
from src.api.order_requests.application import order_request_cases
from src.api.order_requests.domain import (
    OrderRequestAccessDenied,
    OrderRequestCannotAccept,
    OrderRequestCardListingNotFound,
    OrderRequestCreate,
    OrderRequestEventType,
    OrderRequestItemAlreadyExists,
    OrderRequestItemCannotBeAdded,
    OrderRequestItemCannotBeRestored,
    OrderRequestItemCreate,
    OrderRequestItemPricingUpdate,
    OrderRequestItemUpdate,
    OrderRequestNotEditable,
    OrderRequestInvalidTransition,
    OrderRequestNotFound,
    OrderRequestPeriodNotOpen,
    OrderRequestStatus,
    OrderRequestUpdate,
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
class FakeDB:
    commits: int = 0
    rollbacks: int = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@dataclass
class FakePeriod:
    id: int = 4
    opens_at: datetime = NOW - timedelta(days=1)
    closes_at: datetime = NOW + timedelta(days=7)


@dataclass
class FakeListing:
    id: int
    name: str = "Blue-Eyes White Dragon"
    ygo_set: str = "Legend of Blue Eyes White Dragon"
    code: str = "LOB-001"
    rarity: str = "Ultra Rare"
    condition: str = "Near Mint"
    price: Decimal = Decimal("8.50")


@dataclass
class FakeRequest:
    id: int = 17
    order_period_id: int = 4
    created_by_user_id: int = USER.user_id
    status: str = "submitted"
    note: str | None = None
    currency: str = "USD"
    cancelled_at: datetime | None = None
    cancelled_by_user_id: int | None = None
    items: list[object] = field(default_factory=list)
    date_added: datetime = NOW
    date_updated: datetime | None = None


def fake_item(
    *,
    item_id: int = 1,
    listing_id: int = 5,
    removed_at: datetime | None = None,
    priced: bool = False,
) -> SimpleNamespace:
    price = Decimal("1.00") if priced else None
    return SimpleNamespace(
        id=item_id,
        card_listing_id=listing_id,
        card_name="Blue-Eyes White Dragon",
        card_set="Legend of Blue Eyes White Dragon",
        card_code="LOB-001",
        rarity="Ultra Rare",
        condition="Near Mint",
        estimated_unit_price=Decimal("8.50"),
        requested_quantity=2,
        agreed_quantity=2,
        card_unit_price=price,
        shipping_unit_price=price,
        tax_unit_price=price,
        removed_at=removed_at,
        removed_by_user_id=USER.user_id if removed_at else None,
        date_added=NOW,
        date_updated=None,
    )


class PeriodDAO:
    def __init__(self, period: FakePeriod | object = Empty):
        self.period = period
        self.locked: list[int] = []

    async def get_for_update(self, db: object, period_id: int) -> object:
        self.locked.append(period_id)
        return self.period


class ListingDAO:
    def __init__(self, listings: dict[int, FakeListing]):
        self.listings = listings
        self.requested: list[int] = []

    async def get(self, db: object, listing_id: int) -> object:
        self.requested.append(listing_id)
        return self.listings.get(listing_id, Empty)


class RequestDAO:
    def __init__(self, request: FakeRequest | object = Empty, *, fail: bool = False):
        self.request = request
        self.fail = fail
        self.created: list[dict[str, object]] = []
        self.list_args: dict[str, object] | None = None
        self.locked: list[int] = []
        self.flushes = 0

    async def create(self, db: object, **kwargs: object) -> FakeRequest:
        if self.fail:
            raise DAOError
        self.created.append(kwargs)
        self.request = FakeRequest(**kwargs)
        return self.request

    async def get(self, db: object, request_id: int) -> object:
        return self.request

    async def get_for_update(self, db: object, request_id: int) -> object:
        self.locked.append(request_id)
        return self.request

    async def flush(self, db: object) -> None:
        self.flushes += 1

    async def get_multi(self, db: object, **kwargs: object) -> tuple[list[object], int]:
        self.list_args = kwargs
        return ([self.request] if self.request is not Empty else [], 1)


class ItemDAO:
    def __init__(self):
        self.created: list[dict[str, object]] = []

    async def create_from_listing(self, db: object, **kwargs: object) -> object:
        self.created.append(kwargs)
        listing = kwargs["listing"]
        quantity = kwargs["requested_quantity"]
        return SimpleNamespace(
            id=len(self.created),
            card_listing_id=listing.id,
            card_name=listing.name,
            card_set=listing.ygo_set,
            card_code=listing.code,
            rarity=listing.rarity,
            condition=listing.condition,
            estimated_unit_price=listing.price,
            requested_quantity=quantity,
            agreed_quantity=quantity,
            card_unit_price=None,
            shipping_unit_price=None,
            tax_unit_price=None,
            removed_at=None,
            removed_by_user_id=None,
            date_added=NOW,
            date_updated=None,
        )


class HistoryDAO:
    def __init__(self):
        self.created: list[dict[str, object]] = []

    async def create(self, db: object, **kwargs: object) -> object:
        self.created.append(kwargs)
        return object()

    async def get_for_request(self, db: object, **kwargs: object) -> list[object]:
        return [
            SimpleNamespace(
                id=1,
                order_request_id=17,
                event="created",
                actor_user_id=USER.user_id,
                occurred_at=NOW,
                changes=[],
            )
        ]


def install_daos(
    monkeypatch: pytest.MonkeyPatch,
    *,
    period: FakePeriod | object = FakePeriod(),
    listings: dict[int, FakeListing] | None = None,
    request: FakeRequest | object = Empty,
    fail_request: bool = False,
) -> tuple[PeriodDAO, ListingDAO, RequestDAO, ItemDAO, HistoryDAO]:
    daos = (
        PeriodDAO(period),
        ListingDAO(listings or {5: FakeListing(5)}),
        RequestDAO(request, fail=fail_request),
        ItemDAO(),
        HistoryDAO(),
    )
    monkeypatch.setattr(order_request_cases, "period_dao", daos[0])
    monkeypatch.setattr(order_request_cases, "listing_dao", daos[1])
    monkeypatch.setattr(order_request_cases, "request_dao", daos[2])
    monkeypatch.setattr(order_request_cases, "item_dao", daos[3])
    monkeypatch.setattr(order_request_cases, "history_dao", daos[4])
    monkeypatch.setattr(order_request_cases, "datetime_now", lambda: NOW)
    return daos


@pytest.mark.anyio
async def test_create_persists_request_items_and_history_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period_dao, listing_dao, request_dao, item_dao, history_dao = install_daos(
        monkeypatch
    )
    db = FakeDB()
    contract = OrderRequestCreate.model_validate(
        {
            "orderPeriodId": 4,
            "note": "Primera edición",
            "items": [{"cardListingId": 5, "requestedQuantity": 2}],
        }
    )

    result = await order_request_cases.create(db, USER, contract)

    assert isinstance(result, Ok)
    assert result.value.status is OrderRequestStatus.SUBMITTED
    assert period_dao.locked == [4]
    assert listing_dao.requested == [5]
    assert request_dao.created[0]["created_by_user_id"] == USER.user_id
    assert item_dao.created[0]["requested_quantity"] == 2
    assert history_dao.created[0]["event"] is OrderRequestEventType.CREATED
    assert db.commits == 1
    assert db.rollbacks == 0


@pytest.mark.anyio
async def test_create_rejects_a_missing_period(monkeypatch: pytest.MonkeyPatch) -> None:
    install_daos(monkeypatch, period=Empty)

    result = await order_request_cases.create(
        FakeDB(),
        USER,
        OrderRequestCreate.model_validate(
            {
                "orderPeriodId": 404,
                "items": [{"cardListingId": 5, "requestedQuantity": 1}],
            }
        ),
    )

    assert result == Err(OrderPeriodNotFound(404))


@pytest.mark.anyio
async def test_create_rejects_a_period_that_is_not_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(
        monkeypatch,
        period=FakePeriod(opens_at=NOW + timedelta(days=1)),
    )

    result = await order_request_cases.create(
        FakeDB(),
        USER,
        OrderRequestCreate.model_validate(
            {
                "orderPeriodId": 4,
                "items": [{"cardListingId": 5, "requestedQuantity": 1}],
            }
        ),
    )

    assert result == Err(OrderRequestPeriodNotOpen(4))


@pytest.mark.anyio
async def test_create_validates_all_listings_before_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, request_dao, _, _ = install_daos(monkeypatch, listings={})

    result = await order_request_cases.create(
        FakeDB(),
        USER,
        OrderRequestCreate.model_validate(
            {
                "orderPeriodId": 4,
                "items": [{"cardListingId": 99, "requestedQuantity": 1}],
            }
        ),
    )

    assert result == Err(OrderRequestCardListingNotFound(99))
    assert request_dao.created == []


@pytest.mark.anyio
async def test_create_rolls_back_repository_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, fail_request=True)
    db = FakeDB()

    with pytest.raises(DAOError):
        await order_request_cases.create(
            db,
            USER,
            OrderRequestCreate.model_validate(
                {
                    "orderPeriodId": 4,
                    "items": [{"cardListingId": 5, "requestedQuantity": 1}],
                }
            ),
        )

    assert db.rollbacks == 1
    assert db.commits == 0


@pytest.mark.anyio
async def test_regular_user_list_is_filtered_to_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest()
    _, _, request_dao, _, _ = install_daos(monkeypatch, request=request)

    result = await order_request_cases.get_multi(
        object(), USER, page=2, shows=10, order_period_id=4, status=None
    )

    assert isinstance(result, Ok)
    assert request_dao.list_args == {
        "page": 10,
        "shows": 10,
        "owner_user_id": USER.user_id,
        "order_period_id": 4,
        "status": None,
    }


@pytest.mark.anyio
async def test_admin_list_is_not_filtered_to_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, request_dao, _, _ = install_daos(monkeypatch, request=FakeRequest())

    result = await order_request_cases.get_multi(
        object(), ADMIN, page=1, shows=100, order_period_id=None, status=None
    )

    assert isinstance(result, Ok)
    assert request_dao.list_args is not None
    assert request_dao.list_args["owner_user_id"] is None


@pytest.mark.anyio
async def test_actor_without_read_permission_is_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, request=FakeRequest())
    actor = Actor(user_id=9, permissions=frozenset())

    result = await order_request_cases.get_multi(
        object(), actor, page=1, shows=10, order_period_id=None, status=None
    )

    assert result == Err(OrderRequestAccessDenied())


@pytest.mark.anyio
async def test_foreign_request_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    install_daos(monkeypatch, request=FakeRequest(created_by_user_id=99))

    result = await order_request_cases.get_one(object(), USER, 17)

    assert result == Err(OrderRequestNotFound(17))


@pytest.mark.anyio
async def test_get_one_rejects_actor_without_read_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, request=FakeRequest())
    actor = Actor(user_id=9, permissions=frozenset())

    result = await order_request_cases.get_one(object(), actor, 17)

    assert result == Err(OrderRequestAccessDenied())


@pytest.mark.anyio
async def test_owner_can_read_history(monkeypatch: pytest.MonkeyPatch) -> None:
    install_daos(monkeypatch, request=FakeRequest())

    result = await order_request_cases.get_history(
        object(), USER, 17, page=1, shows=25
    )

    assert isinstance(result, Ok)
    assert result.value[0].event is OrderRequestEventType.CREATED


@pytest.mark.anyio
async def test_update_note_locks_audits_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(note="Antes", items=[fake_item()])
    _, _, request_dao, _, history_dao = install_daos(
        monkeypatch, request=request
    )
    db = FakeDB()

    result = await order_request_cases.update_note(
        db, USER, 17, OrderRequestUpdate(note="Después")
    )

    assert isinstance(result, Ok)
    assert request_dao.locked == [17]
    assert request.note == "Después"
    assert history_dao.created[-1]["event"] is OrderRequestEventType.UPDATED
    assert history_dao.created[-1]["changes"] == [
        {"field": "note", "oldValue": "Antes", "newValue": "Después"}
    ]
    assert request_dao.flushes == db.commits == 1


@pytest.mark.anyio
async def test_noop_update_does_not_write_history_or_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(note="Igual", items=[fake_item()])
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)
    db = FakeDB()

    result = await order_request_cases.update_note(
        db, USER, 17, OrderRequestUpdate(note="Igual")
    )

    assert isinstance(result, Ok)
    assert history_dao.created == []
    assert db.commits == 0


@pytest.mark.anyio
async def test_foreign_order_is_hidden_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, request=FakeRequest(created_by_user_id=99))

    result = await order_request_cases.update_note(
        FakeDB(), USER, 17, OrderRequestUpdate(note="No permitido")
    )

    assert result == Err(OrderRequestNotFound(17))


@pytest.mark.anyio
async def test_rejected_order_requires_reopening_before_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.REJECTED, items=[fake_item()]),
    )

    result = await order_request_cases.update_item(
        FakeDB(), USER, 17, 1, OrderRequestItemUpdate(requested_quantity=3)
    )

    assert result == Err(OrderRequestNotEditable(OrderRequestStatus.REJECTED))


@pytest.mark.anyio
async def test_update_item_after_acceptance_keeps_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(
        status=OrderRequestStatus.ACCEPTED, items=[fake_item(priced=True)]
    )
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)

    result = await order_request_cases.update_item(
        FakeDB(), USER, 17, 1, OrderRequestItemUpdate(agreed_quantity=1)
    )

    assert isinstance(result, Ok)
    assert request.status is OrderRequestStatus.ACCEPTED
    assert request.items[0].agreed_quantity == 1
    assert history_dao.created[-1]["event"] is OrderRequestEventType.ITEM_UPDATED


@pytest.mark.anyio
async def test_add_item_rejects_accepted_and_existing_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = OrderRequestItemCreate(card_listing_id=5, requested_quantity=1)
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.ACCEPTED, items=[fake_item()]),
    )
    accepted_result = await order_request_cases.add_item(
        FakeDB(), USER, 17, contract
    )
    assert accepted_result == Err(
        OrderRequestItemCannotBeAdded(OrderRequestStatus.ACCEPTED)
    )

    install_daos(monkeypatch, request=FakeRequest(items=[fake_item(removed_at=NOW)]))
    duplicate_result = await order_request_cases.add_item(
        FakeDB(), USER, 17, contract
    )
    assert duplicate_result == Err(OrderRequestItemAlreadyExists(17, 5))


@pytest.mark.anyio
async def test_add_item_copies_snapshot_and_audits_in_one_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(items=[])
    _, listing_dao, request_dao, item_dao, history_dao = install_daos(
        monkeypatch,
        request=request,
        listings={7: FakeListing(7)},
    )
    db = FakeDB()

    result = await order_request_cases.add_item(
        db,
        USER,
        17,
        OrderRequestItemCreate(card_listing_id=7, requested_quantity=3),
    )

    assert isinstance(result, Ok)
    assert request_dao.locked == [17]
    assert listing_dao.requested == [7]
    assert item_dao.created[0]["requested_quantity"] == 3
    assert result.value.items[0].agreed_quantity == 3
    assert history_dao.created[-1]["event"] is OrderRequestEventType.ITEM_ADDED
    assert db.commits == 1


@pytest.mark.anyio
async def test_remove_last_active_item_cancels_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(items=[fake_item()])
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)
    db = FakeDB()

    result = await order_request_cases.remove_item(db, USER, 17, 1)

    assert isinstance(result, Ok)
    assert result.value.items == []
    assert request.status is OrderRequestStatus.CANCELLED
    assert request.cancelled_at == NOW
    assert [entry["event"] for entry in history_dao.created] == [
        OrderRequestEventType.ITEM_REMOVED,
        OrderRequestEventType.STATUS_CHANGED,
    ]
    assert db.commits == 1


@pytest.mark.anyio
async def test_restore_in_accepted_order_requires_complete_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unpriced = fake_item(removed_at=NOW)
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.ACCEPTED, items=[unpriced]),
    )
    blocked = await order_request_cases.restore_item(FakeDB(), USER, 17, 1)
    assert blocked == Err(
        OrderRequestItemCannotBeRestored(OrderRequestStatus.ACCEPTED)
    )

    priced = fake_item(removed_at=NOW, priced=True)
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.ACCEPTED, items=[priced]),
    )
    restored = await order_request_cases.restore_item(FakeDB(), USER, 17, 1)
    assert isinstance(restored, Ok)
    assert restored.value.items[0].id == 1


@pytest.mark.anyio
async def test_compound_mutation_rolls_back_when_history_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(items=[fake_item()])
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)

    async def fail_history(*args: object, **kwargs: object) -> object:
        raise DAOError

    monkeypatch.setattr(history_dao, "create", fail_history)
    db = FakeDB()

    with pytest.raises(DAOError):
        await order_request_cases.remove_item(db, USER, 17, 1)

    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.mark.anyio
async def test_admin_can_start_review_and_status_change_is_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(status=OrderRequestStatus.SUBMITTED, items=[fake_item()])
    _, _, request_dao, _, history_dao = install_daos(monkeypatch, request=request)
    db = FakeDB()

    result = await order_request_cases.start_review(db, ADMIN, 17)

    assert isinstance(result, Ok)
    assert request_dao.locked == [17]
    assert request.status is OrderRequestStatus.IN_REVIEW
    assert history_dao.created[-1]["event"] is OrderRequestEventType.STATUS_CHANGED
    assert history_dao.created[-1]["changes"] == [
        {"field": "status", "oldValue": "submitted", "newValue": "in_review"}
    ]
    assert db.commits == 1


@pytest.mark.anyio
async def test_review_actions_require_review_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(monkeypatch, request=FakeRequest(items=[fake_item()]))

    result = await order_request_cases.start_review(FakeDB(), USER, 17)

    assert result == Err(OrderRequestAccessDenied())


@pytest.mark.anyio
async def test_status_transition_rolls_back_with_its_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(status=OrderRequestStatus.SUBMITTED, items=[fake_item()])
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)

    async def fail_history(*args: object, **kwargs: object) -> object:
        raise DAOError

    monkeypatch.setattr(history_dao, "create", fail_history)
    db = FakeDB()
    with pytest.raises(DAOError):
        await order_request_cases.start_review(db, ADMIN, 17)

    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.mark.anyio
async def test_accept_requires_in_review_active_and_fully_priced_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.SUBMITTED, items=[fake_item(priced=True)]),
    )
    wrong_state = await order_request_cases.accept(FakeDB(), ADMIN, 17)
    assert wrong_state == Err(
        OrderRequestInvalidTransition(
            OrderRequestStatus.SUBMITTED, OrderRequestStatus.ACCEPTED
        )
    )

    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.IN_REVIEW, items=[]),
    )
    empty = await order_request_cases.accept(FakeDB(), ADMIN, 17)
    assert empty == Err(OrderRequestCannotAccept("no_active_items"))

    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.IN_REVIEW, items=[fake_item()]),
    )
    incomplete = await order_request_cases.accept(FakeDB(), ADMIN, 17)
    assert incomplete == Err(OrderRequestCannotAccept("incomplete_pricing"))


@pytest.mark.anyio
async def test_accept_succeeds_with_zero_price_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = fake_item(priced=True)
    item.shipping_unit_price = Decimal("0.00")
    item.tax_unit_price = Decimal("0.00")
    request = FakeRequest(status=OrderRequestStatus.IN_REVIEW, items=[item])
    install_daos(monkeypatch, request=request)

    result = await order_request_cases.accept(FakeDB(), ADMIN, 17)

    assert isinstance(result, Ok)
    assert result.value.status is OrderRequestStatus.ACCEPTED
    assert result.value.agreed_total == Decimal("2.00")


@pytest.mark.anyio
async def test_reject_and_reopen_follow_explicit_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(status=OrderRequestStatus.IN_REVIEW, items=[fake_item()])
    install_daos(monkeypatch, request=request)
    rejected = await order_request_cases.reject(FakeDB(), ADMIN, 17)
    assert isinstance(rejected, Ok)
    assert request.status is OrderRequestStatus.REJECTED

    reopened = await order_request_cases.reopen_for_review(FakeDB(), ADMIN, 17)
    assert isinstance(reopened, Ok)
    assert request.status is OrderRequestStatus.IN_REVIEW

    invalid = await order_request_cases.reopen_for_review(FakeDB(), ADMIN, 17)
    assert invalid == Err(
        OrderRequestInvalidTransition(
            OrderRequestStatus.IN_REVIEW, OrderRequestStatus.IN_REVIEW
        )
    )

    cancelled_request = FakeRequest(
        status=OrderRequestStatus.CANCELLED,
        cancelled_at=NOW,
        cancelled_by_user_id=USER.user_id,
        items=[],
    )
    _, _, _, _, history_dao = install_daos(
        monkeypatch,
        request=cancelled_request,
    )
    reopened_cancelled = await order_request_cases.reopen_for_review(
        FakeDB(), ADMIN, 17
    )
    assert isinstance(reopened_cancelled, Ok)
    assert cancelled_request.cancelled_at is None
    assert cancelled_request.cancelled_by_user_id is None
    assert {change["field"] for change in history_dao.created[-1]["changes"]} == {
        "status",
        "cancelledAt",
        "cancelledByUserId",
    }


@pytest.mark.anyio
async def test_owner_can_cancel_accepted_but_not_foreign_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(status=OrderRequestStatus.ACCEPTED, items=[fake_item(priced=True)])
    install_daos(monkeypatch, request=request)
    cancelled = await order_request_cases.cancel(FakeDB(), USER, 17)
    assert isinstance(cancelled, Ok)
    assert request.status is OrderRequestStatus.CANCELLED
    assert request.cancelled_at == NOW

    install_daos(
        monkeypatch,
        request=FakeRequest(
            created_by_user_id=99,
            status=OrderRequestStatus.SUBMITTED,
            items=[fake_item()],
        ),
    )
    foreign = await order_request_cases.cancel(FakeDB(), USER, 17)
    assert foreign == Err(OrderRequestNotFound(17))


@pytest.mark.anyio
async def test_admin_cancel_respects_transition_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_daos(
        monkeypatch,
        request=FakeRequest(status=OrderRequestStatus.ACCEPTED, items=[fake_item(priced=True)]),
    )

    result = await order_request_cases.cancel(FakeDB(), ADMIN, 17)

    assert result == Err(
        OrderRequestInvalidTransition(
            OrderRequestStatus.ACCEPTED, OrderRequestStatus.CANCELLED
        )
    )


@pytest.mark.anyio
async def test_pricing_updates_active_accepted_order_without_changing_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = FakeRequest(
        status=OrderRequestStatus.ACCEPTED,
        items=[fake_item(priced=True)],
    )
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)

    result = await order_request_cases.update_pricing(
        FakeDB(),
        ADMIN,
        17,
        1,
        OrderRequestItemPricingUpdate(
            card_unit_price=Decimal("2.005"),
            shipping_unit_price=Decimal("0"),
            tax_unit_price=Decimal("0.10"),
        ),
    )

    assert isinstance(result, Ok)
    assert request.status is OrderRequestStatus.ACCEPTED
    assert request.items[0].card_unit_price == Decimal("2.01")
    assert result.value.agreed_total == Decimal("4.22")
    assert history_dao.created[-1]["event"] is OrderRequestEventType.ITEM_UPDATED


@pytest.mark.anyio
async def test_pricing_noop_has_no_history_and_failure_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = fake_item(priced=True)
    request = FakeRequest(status=OrderRequestStatus.IN_REVIEW, items=[item])
    _, _, _, _, history_dao = install_daos(monkeypatch, request=request)
    same = OrderRequestItemPricingUpdate(
        card_unit_price=Decimal("1"),
        shipping_unit_price=Decimal("1"),
        tax_unit_price=Decimal("1"),
    )
    db = FakeDB()
    noop = await order_request_cases.update_pricing(db, ADMIN, 17, 1, same)
    assert isinstance(noop, Ok)
    assert history_dao.created == []
    assert db.commits == 0

    async def fail_history(*args: object, **kwargs: object) -> object:
        raise DAOError

    monkeypatch.setattr(history_dao, "create", fail_history)
    changed = OrderRequestItemPricingUpdate(
        card_unit_price=Decimal("2"),
        shipping_unit_price=Decimal("1"),
        tax_unit_price=Decimal("1"),
    )
    with pytest.raises(DAOError):
        await order_request_cases.update_pricing(db, ADMIN, 17, 1, changed)
    assert db.rollbacks == 1
