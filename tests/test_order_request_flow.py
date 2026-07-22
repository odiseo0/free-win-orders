from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.order_requests.application import order_request_cases
from src.api.order_requests.domain import OrderRequestEventType, OrderRequestStatus
from src.api.roles.domain import Actor, PermissionCode, USER_PERMISSIONS
from src.api.roles.infrastructure.auth import get_current_user
from src.application import app
from src.core.db import get_db
from src.core.utils.utils import Empty


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
OWNER = Actor(user_id=2, permissions=USER_PERMISSIONS)
OTHER_USER = Actor(user_id=3, permissions=USER_PERMISSIONS)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeDB:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class PeriodDAO:
    async def get_for_update(self, db: object, period_id: int) -> object:
        if period_id != 4:
            return Empty
        return SimpleNamespace(
            id=4,
            opens_at=NOW - timedelta(days=1),
            closes_at=NOW + timedelta(days=1),
        )


class ListingDAO:
    async def get(self, db: object, listing_id: int) -> object:
        if listing_id != 5:
            return Empty
        return SimpleNamespace(
            id=5,
            name="Blue-Eyes White Dragon",
            ygo_set="Legend of Blue Eyes White Dragon",
            code="LOB-001",
            rarity="Ultra Rare",
            condition="Near Mint",
            price=Decimal("8.50"),
        )


class RequestDAO:
    def __init__(self) -> None:
        self.request: object = Empty

    async def create(self, db: object, **values: object) -> object:
        self.request = SimpleNamespace(
            id=17,
            status=OrderRequestStatus.SUBMITTED,
            currency="USD",
            cancelled_at=None,
            cancelled_by_user_id=None,
            items=[],
            date_added=NOW,
            date_updated=None,
            **values,
        )
        return self.request

    async def get(self, db: object, order_request_id: int) -> object:
        if self.request is Empty or order_request_id != self.request.id:
            return Empty
        return self.request

    async def get_for_update(self, db: object, order_request_id: int) -> object:
        return await self.get(db, order_request_id)

    async def get_multi(
        self,
        db: object,
        *,
        owner_user_id: int | None,
        order_period_id: int | None,
        status: OrderRequestStatus | None,
        **pagination: object,
    ) -> tuple[list[object], int]:
        if self.request is Empty:
            return [], 0
        visible = (
            (owner_user_id is None or self.request.created_by_user_id == owner_user_id)
            and (order_period_id is None or self.request.order_period_id == order_period_id)
            and (status is None or self.request.status == status)
        )
        return ([self.request], 1) if visible else ([], 0)

    async def flush(self, db: object) -> None:
        pass


class ItemDAO:
    async def create_from_listing(
        self,
        db: object,
        *,
        order_request_id: int,
        listing: object,
        requested_quantity: int,
    ) -> object:
        return SimpleNamespace(
            id=1,
            order_request_id=order_request_id,
            card_listing_id=listing.id,
            card_name=listing.name,
            card_set=listing.ygo_set,
            card_code=listing.code,
            rarity=listing.rarity,
            condition=listing.condition,
            estimated_unit_price=listing.price,
            requested_quantity=requested_quantity,
            agreed_quantity=requested_quantity,
            card_unit_price=None,
            shipping_unit_price=None,
            tax_unit_price=None,
            removed_at=None,
            removed_by_user_id=None,
            date_added=NOW,
            date_updated=None,
        )


class HistoryDAO:
    def __init__(self) -> None:
        self.entries: list[object] = []

    async def create(
        self,
        db: object,
        *,
        order_request_id: int,
        event: OrderRequestEventType,
        actor_user_id: int,
        changes: list[dict[str, object]],
        occurred_at: datetime | None = None,
    ) -> object:
        entry = SimpleNamespace(
            id=len(self.entries) + 1,
            order_request_id=order_request_id,
            event=event,
            actor_user_id=actor_user_id,
            occurred_at=occurred_at or NOW,
            changes=changes,
        )
        self.entries.append(entry)
        return entry

    async def get_for_request(
        self,
        db: object,
        *,
        order_request_id: int,
        page: int,
        shows: int,
    ) -> list[object]:
        entries = [
            entry
            for entry in reversed(self.entries)
            if entry.order_request_id == order_request_id
        ]
        return entries[page : page + shows]


@pytest.mark.anyio
async def test_complete_v1_http_flow_and_owner_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeDB()
    current_actor = {"value": OWNER}
    request_dao = RequestDAO()
    history_dao = HistoryDAO()

    async def override_db() -> AsyncIterator[FakeDB]:
        yield db

    async def override_actor() -> Actor:
        return current_actor["value"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_actor
    monkeypatch.setattr(order_request_cases, "period_dao", PeriodDAO())
    monkeypatch.setattr(order_request_cases, "listing_dao", ListingDAO())
    monkeypatch.setattr(order_request_cases, "request_dao", request_dao)
    monkeypatch.setattr(order_request_cases, "item_dao", ItemDAO())
    monkeypatch.setattr(order_request_cases, "history_dao", history_dao)
    monkeypatch.setattr(order_request_cases, "datetime_now", lambda: NOW)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/order-requests/",
                json={
                    "orderPeriodId": 4,
                    "note": "Primera edición",
                    "items": [{"cardListingId": 5, "requestedQuantity": 2}],
                },
            )
            assert created.status_code == 201
            assert created.json()["createdByUserId"] == OWNER.user_id

            current_actor["value"] = OTHER_USER
            hidden = await client.get("/order-requests/17")
            hidden_history = await client.get("/order-requests/17/history")
            isolated_list = await client.get("/order-requests/")
            assert hidden.status_code == hidden_history.status_code == 404
            assert isolated_list.json() == {"items": [], "total": 0}
            assert "Primera edición" not in hidden.text + hidden_history.text

            current_actor["value"] = ADMIN
            reviewed = await client.post("/order-requests/17/start-review")
            assert reviewed.json()["status"] == "in_review"
            priced = await client.patch(
                "/order-requests/17/items/1/pricing",
                json={
                    "cardUnitPrice": "2.00",
                    "shippingUnitPrice": "0.50",
                    "taxUnitPrice": "0.10",
                },
            )
            assert priced.json()["items"][0]["finalUnitPrice"] == "2.60"
            accepted = await client.post("/order-requests/17/accept")
            assert accepted.json()["status"] == "accepted"
            assert accepted.json()["agreedTotal"] == "5.20"

            current_actor["value"] = OWNER
            adjusted = await client.patch(
                "/order-requests/17/items/1",
                json={"agreedQuantity": 1},
            )
            assert adjusted.json()["status"] == "accepted"
            assert adjusted.json()["agreedTotal"] == "2.60"
            history = await client.get("/order-requests/17/history")
            assert history.status_code == 200
            assert {entry["event"] for entry in history.json()} >= {
                "created",
                "status_changed",
                "item_updated",
            }
            assert "password" not in history.text
            assert "email" not in history.text
    finally:
        app.dependency_overrides.clear()
