from types import SimpleNamespace
from datetime import UTC, datetime

import pytest

from src.api.deliveries.application import cases
from src.api.deliveries.domain import NationalCarrier, ProviderTrackingError
from src.api.deliveries.providers import UnconfiguredTrackingProvider
from src.api.order_requests.domain import OrderRequestStatus
from src.api.roles.domain import Actor, PermissionCode
from src.core import Err, Ok

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeDB:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeRequestDAO:
    def __init__(self, request: SimpleNamespace) -> None:
        self.request = request
        self.flushed = 0

    async def get_for_update(self, db: object, request_id: int) -> SimpleNamespace:
        return self.request

    async def flush(self, db: object) -> None:
        self.flushed += 1


class FakeHistoryDAO:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    async def create(self, db: object, **values: object) -> SimpleNamespace:
        self.entries.append(values)
        return SimpleNamespace(**values)


@pytest.mark.anyio
async def test_mark_paid_changes_status_and_audits_atomically(monkeypatch) -> None:
    request = SimpleNamespace(
        id=9,
        status=OrderRequestStatus.ACCEPTED,
        paid_at=None,
        paid_by_user_id=None,
    )
    request_dao = FakeRequestDAO(request)
    history_dao = FakeHistoryDAO()
    monkeypatch.setattr(cases, "dao_order_requests", request_dao)
    monkeypatch.setattr(cases, "dao_order_request_histories", history_dao)
    monkeypatch.setattr(cases, "_order_response", lambda value: value)
    db = FakeDB()
    actor = Actor(
        user_id=3,
        permissions=frozenset({PermissionCode.DELIVERIES_MANAGE_PAYMENTS}),
    )

    result = await cases.mark_paid(db, actor, 9)

    assert isinstance(result, Ok)
    assert request.status is OrderRequestStatus.PAID
    assert request.paid_at is not None
    assert request.paid_by_user_id == 3
    assert history_dao.entries[0]["changes"][0] == {
        "field": "status",
        "oldValue": "accepted",
        "newValue": "paid",
    }
    assert request_dao.flushed == 1
    assert db.commits == 1


@pytest.mark.anyio
async def test_mark_paid_rejects_wrong_state_without_writing(monkeypatch) -> None:
    request = SimpleNamespace(id=9, status=OrderRequestStatus.IN_REVIEW)
    request_dao = FakeRequestDAO(request)
    monkeypatch.setattr(cases, "dao_order_requests", request_dao)
    db = FakeDB()
    actor = Actor(
        user_id=3,
        permissions=frozenset({PermissionCode.DELIVERIES_MANAGE_PAYMENTS}),
    )

    result = await cases.mark_paid(db, actor, 9)

    assert isinstance(result, Err)
    assert result.error.reason == "invalid_payment_transition"
    assert request_dao.flushed == 0
    assert db.commits == 0


@pytest.mark.anyio
async def test_unconfigured_carriers_make_no_network_request() -> None:
    provider = UnconfiguredTrackingProvider(NationalCarrier.ZOOM)

    result = await provider.fetch("TEST-123")

    assert result == Err(ProviderTrackingError("provider_not_configured"))


def test_shipment_response_hides_other_order_allocations() -> None:
    stage = SimpleNamespace(
        id=1,
        scope="international",
        key="purchase_confirmed",
        name="Compra confirmada",
        position=0,
        kind="progress",
        is_terminal=False,
        is_active=True,
    )
    shipment = SimpleNamespace(
        id=5,
        order_period_id=4,
        name="Compra compartida",
        reference=None,
        external_references=[],
        current_stage=stage,
        allocations=[
            SimpleNamespace(order_request_id=8, order_request_item_id=10, quantity=1),
            SimpleNamespace(order_request_id=9, order_request_item_id=11, quantity=2),
        ],
        events=[],
        date_added=NOW,
        date_updated=None,
    )

    response = cases._shipment_response(
        shipment, visible_order_request_ids={8}
    )

    assert [item.order_request_id for item in response.allocations] == [8]
