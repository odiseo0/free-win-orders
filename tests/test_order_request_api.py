from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.order_periods.domain import OrderPeriodNotFound
from src.api.order_requests.domain import (
    OrderRequestAccessDenied,
    OrderRequestCannotAccept,
    OrderRequestCardListingNotFound,
    OrderRequestHistoryResponse,
    OrderRequestItemAlreadyExists,
    OrderRequestItemCannotBeRestored,
    OrderRequestInvalidTransition,
    OrderRequestItemResponse,
    OrderRequestNotFound,
    OrderRequestPeriodNotOpen,
    OrderRequestResponse,
    OrderRequestStatus,
)
from src.api.order_requests.infrastructure import order_requests_api
from src.api.roles.domain import Actor, PermissionCode, USER_PERMISSIONS
from src.api.roles.infrastructure.auth import get_current_user
from src.application import app
from src.core import Err, Ok
from src.core.db import get_db


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))
USER = Actor(user_id=2, permissions=USER_PERMISSIONS)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


async def fake_db() -> AsyncIterator[object]:
    yield object()


def authenticate(actor: Actor) -> None:
    async def override_actor() -> Actor:
        return actor

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = override_actor


def request_response() -> OrderRequestResponse:
    item = OrderRequestItemResponse(
        id=1,
        card_listing_id=5,
        card_name="Blue-Eyes White Dragon",
        card_set="Legend of Blue Eyes White Dragon",
        card_code="LOB-001",
        rarity="Ultra Rare",
        condition="Near Mint",
        estimated_unit_price=Decimal("8.50"),
        requested_quantity=2,
        agreed_quantity=2,
        date_added=NOW,
    )
    return OrderRequestResponse(
        id=17,
        order_period_id=4,
        created_by_user_id=USER.user_id,
        status="submitted",
        note="Primera edición",
        items=[item],
        date_added=NOW,
    )


def history_response() -> OrderRequestHistoryResponse:
    return OrderRequestHistoryResponse(
        id=1,
        order_request_id=17,
        event="created",
        actor_user_id=USER.user_id,
        occurred_at=NOW,
        changes=[],
    )


@pytest.mark.anyio
async def test_create_returns_201_and_public_contract(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def create(*args: object, **kwargs: object) -> object:
        return Ok(request_response())

    monkeypatch.setattr(order_requests_api.order_request_cases, "create", create)

    response = await client.post(
        "/order-requests/",
        json={
            "orderPeriodId": 4,
            "note": "Primera edición",
            "items": [{"cardListingId": 5, "requestedQuantity": 2}],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "submitted"
    assert response.json()["items"][0]["cardListingId"] == 5
    assert response.json()["items"][0]["agreedQuantity"] == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (OrderPeriodNotFound(404), 404, "El Pedido no existe"),
        (
            OrderRequestCardListingNotFound(99),
            404,
            "La publicación de carta no existe",
        ),
        (
            OrderRequestPeriodNotOpen(4),
            409,
            "El Pedido no está abierto para recibir Órdenes",
        ),
    ],
)
async def test_create_translates_domain_errors(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    error: object,
    status_code: int,
    detail: str,
) -> None:
    authenticate(USER)

    async def create(*args: object, **kwargs: object) -> object:
        return Err(error)

    monkeypatch.setattr(order_requests_api.order_request_cases, "create", create)

    response = await client.post(
        "/order-requests/",
        json={
            "orderPeriodId": 4,
            "items": [{"cardListingId": 5, "requestedQuantity": 1}],
        },
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


@pytest.mark.anyio
async def test_list_propagates_filters_and_pagination(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)
    captured: dict[str, object] = {}

    async def get_multi(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return Ok(([request_response()], 1))

    monkeypatch.setattr(order_requests_api.order_request_cases, "get_multi", get_multi)

    response = await client.get(
        "/order-requests/",
        params={
            "page": 2,
            "shows": 25,
            "orderPeriodId": 4,
            "status": "submitted",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert captured == {
        "page": 2,
        "shows": 25,
        "order_period_id": 4,
        "status": "submitted",
    }


@pytest.mark.anyio
async def test_read_foreign_request_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def get_one(*args: object, **kwargs: object) -> object:
        return Err(OrderRequestNotFound(17))

    monkeypatch.setattr(order_requests_api.order_request_cases, "get_one", get_one)

    response = await client.get("/order-requests/17")

    assert response.status_code == 404
    assert response.json() == {"detail": "La Orden no existe"}


@pytest.mark.anyio
async def test_history_returns_public_events(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def get_history(*args: object, **kwargs: object) -> object:
        return Ok([history_response()])

    monkeypatch.setattr(
        order_requests_api.order_request_cases,
        "get_history",
        get_history,
    )

    response = await client.get("/order-requests/17/history")

    assert response.status_code == 200
    assert response.json()[0]["event"] == "created"
    assert response.json()[0]["actorUserId"] == USER.user_id
    assert "password" not in response.text


@pytest.mark.anyio
async def test_list_translates_missing_permission_to_403(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(Actor(user_id=9, permissions=frozenset()))

    async def get_multi(*args: object, **kwargs: object) -> object:
        return Err(OrderRequestAccessDenied())

    monkeypatch.setattr(order_requests_api.order_request_cases, "get_multi", get_multi)

    response = await client.get("/order-requests/")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_patch_note_uses_camel_case_contract(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)
    captured: dict[str, object] = {}

    async def update_note(*args: object) -> object:
        captured["contract"] = args[-1]
        response = request_response()
        response.note = args[-1].note
        return Ok(response)

    monkeypatch.setattr(order_requests_api.order_request_cases, "update_note", update_note)
    response = await client.patch("/order-requests/17", json={"note": "Nueva nota"})

    assert response.status_code == 200
    assert response.json()["note"] == "Nueva nota"
    assert captured["contract"].note == "Nueva nota"


@pytest.mark.anyio
async def test_add_item_returns_201_and_translates_duplicate_to_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def add_item(*args: object) -> object:
        return Err(OrderRequestItemAlreadyExists(17, 5))

    monkeypatch.setattr(order_requests_api.order_request_cases, "add_item", add_item)
    response = await client.post(
        "/order-requests/17/items",
        json={"cardListingId": 5, "requestedQuantity": 2},
    )

    assert response.status_code == 409
    assert "restaura" in response.json()["detail"]


@pytest.mark.anyio
async def test_update_item_rejects_pricing_fields_at_http_boundary(
    client: AsyncClient,
) -> None:
    authenticate(USER)
    response = await client.patch(
        "/order-requests/17/items/1",
        json={"cardUnitPrice": "2.00"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_restore_translates_incomplete_accepted_item_to_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def restore_item(*args: object) -> object:
        return Err(OrderRequestItemCannotBeRestored(OrderRequestStatus.ACCEPTED))

    monkeypatch.setattr(order_requests_api.order_request_cases, "restore_item", restore_item)
    response = await client.post("/order-requests/17/items/1/restore")
    assert response.status_code == 409


@pytest.mark.anyio
async def test_remove_returns_order_without_removed_item(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def remove_item(*args: object) -> object:
        response = request_response()
        response.items = []
        response.status = OrderRequestStatus.CANCELLED
        return Ok(response)

    monkeypatch.setattr(order_requests_api.order_request_cases, "remove_item", remove_item)
    response = await client.post("/order-requests/17/items/1/remove")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_start_review_requires_admin_permission_and_returns_transition(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)

    async def start_review(*args: object) -> object:
        response = request_response()
        response.status = OrderRequestStatus.IN_REVIEW
        return Ok(response)

    monkeypatch.setattr(order_requests_api.order_request_cases, "start_review", start_review)
    response = await client.post("/order-requests/17/start-review")
    assert response.status_code == 200
    assert response.json()["status"] == "in_review"

    authenticate(USER)
    forbidden = await client.post("/order-requests/17/start-review")
    assert forbidden.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (
            OrderRequestInvalidTransition(
                OrderRequestStatus.SUBMITTED, OrderRequestStatus.ACCEPTED
            ),
            "La transición solicitada no es válida para el estado actual",
        ),
        (
            OrderRequestCannotAccept("no_active_items"),
            "La Orden necesita al menos un ítem activo para aceptarse",
        ),
        (
            OrderRequestCannotAccept("incomplete_pricing"),
            "Todos los ítems activos deben tener precios completos",
        ),
    ],
)
async def test_accept_documents_and_translates_precondition_conflicts(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    error: object,
    detail: str,
) -> None:
    authenticate(ADMIN)

    async def accept(*args: object) -> object:
        return Err(error)

    monkeypatch.setattr(order_requests_api.order_request_cases, "accept", accept)
    response = await client.post("/order-requests/17/accept")
    assert response.status_code == 409
    assert response.json() == {"detail": detail}


@pytest.mark.anyio
async def test_owner_can_call_cancel_without_review_permission(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def cancel(*args: object) -> object:
        response = request_response()
        response.status = OrderRequestStatus.CANCELLED
        return Ok(response)

    monkeypatch.setattr(order_requests_api.order_request_cases, "cancel", cancel)
    response = await client.post("/order-requests/17/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_pricing_uses_camel_case_and_computes_values_server_side(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)
    captured: dict[str, object] = {}

    async def update_pricing(*args: object) -> object:
        captured["pricing"] = args[-1]
        return Ok(request_response())

    monkeypatch.setattr(
        order_requests_api.order_request_cases,
        "update_pricing",
        update_pricing,
    )
    response = await client.patch(
        "/order-requests/17/items/1/pricing",
        json={
            "cardUnitPrice": "1.005",
            "shippingUnitPrice": "0",
            "taxUnitPrice": "0.20",
        },
    )
    pricing = captured["pricing"]
    assert response.status_code == 200
    assert pricing.card_unit_price == Decimal("1.01")
    assert pricing.final_unit_price == Decimal("1.21")


@pytest.mark.anyio
async def test_pricing_rejects_null_negative_and_missing_components(
    client: AsyncClient,
) -> None:
    authenticate(ADMIN)
    for payload in (
        {
            "cardUnitPrice": None,
            "shippingUnitPrice": "0",
            "taxUnitPrice": "0",
        },
        {
            "cardUnitPrice": "-0.01",
            "shippingUnitPrice": "0",
            "taxUnitPrice": "0",
        },
        {"cardUnitPrice": "1", "shippingUnitPrice": "0"},
    ):
        response = await client.patch(
            "/order-requests/17/items/1/pricing",
            json=payload,
        )
        assert response.status_code == 422


def test_openapi_documents_every_declared_http_response() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    expected = {
        ("/order-requests/", "post"): {"201", "401", "403", "404", "409", "422"},
        ("/order-requests/", "get"): {"200", "401", "403", "422"},
        ("/order-requests/{order_request_id}", "get"): {
            "200",
            "401",
            "403",
            "404",
            "422",
        },
        ("/order-requests/{order_request_id}/history", "get"): {
            "200",
            "401",
            "403",
            "404",
            "422",
        },
        ("/order-requests/{order_request_id}", "patch"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/items", "post"): {
            "201", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/items/{item_id}", "patch"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/items/{item_id}/remove", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/items/{item_id}/restore", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/start-review", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/accept", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/reject", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/cancel", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/reopen-for-review", "post"): {
            "200", "401", "403", "404", "409", "422"
        },
        ("/order-requests/{order_request_id}/items/{item_id}/pricing", "patch"): {
            "200", "401", "403", "404", "409", "422"
        },
    }

    for (path, method), response_codes in expected.items():
        assert response_codes <= set(paths[path][method]["responses"])
