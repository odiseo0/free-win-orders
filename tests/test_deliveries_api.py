from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.deliveries.domain import DeliveryNotFound
from src.api.deliveries.infrastructure import http
from src.api.order_requests.domain import OrderRequestItemResponse, OrderRequestResponse
from src.api.roles.domain import Actor, PermissionCode
from src.api.roles.infrastructure.auth import get_current_user
from src.application import app
from src.core import Err, Ok
from src.core.db import get_db


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.fixture(autouse=True)
def clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


def authenticate() -> None:
    async def fake_db() -> AsyncIterator[object]:
        yield object()

    async def actor() -> Actor:
        return ADMIN

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = actor


def paid_response() -> OrderRequestResponse:
    item = OrderRequestItemResponse(
        id=2,
        card_listing_id=3,
        card_name="Dark Magician",
        card_set="LOB",
        card_code="LOB-005",
        rarity="Ultra Rare",
        condition="Near Mint",
        estimated_unit_price="5.00",
        requested_quantity=1,
        agreed_quantity=1,
        date_added=NOW,
    )
    return OrderRequestResponse(
        id=7,
        order_period_id=4,
        created_by_user_id=2,
        status="paid",
        paid_at=NOW,
        paid_by_user_id=ADMIN.user_id,
        items=[item],
        date_added=NOW,
    )


@pytest.mark.anyio
async def test_mark_paid_returns_the_public_order(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate()

    async def mark_paid(*args: object) -> object:
        return Ok(paid_response())

    monkeypatch.setattr(http.cases, "mark_paid", mark_paid)

    response = await client.post("/order-requests/7/mark-paid")

    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert response.json()["paidAt"] == NOW.isoformat().replace("+00:00", "Z")


@pytest.mark.anyio
async def test_tracking_hides_an_unknown_or_foreign_order(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate()

    async def get_tracking(*args: object) -> object:
        return Err(DeliveryNotFound("order_request", 7))

    monkeypatch.setattr(http.cases, "get_tracking", get_tracking)

    response = await client.get("/order-requests/7/tracking")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_refresh_queues_work_and_returns_an_empty_202(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate()

    async def request_refresh(*args: object) -> object:
        return Ok(None)

    monkeypatch.setattr(http.cases, "request_refresh", request_refresh)

    response = await client.post("/deliveries/national-shipments/5/refresh")

    assert response.status_code == 202
    assert response.content == b""
