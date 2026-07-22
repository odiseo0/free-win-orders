from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.order_periods.domain import (
    OrderPeriodAlreadyClosed,
    OrderPeriodCannotCloseDraft,
    OrderPeriodDateConflict,
    OrderPeriodHistoryResponse,
    OrderPeriodImmutableField,
    OrderPeriodNotFound,
    OrderPeriodResponse,
    OrderPeriodStatus,
)
from src.api.order_periods.infrastructure import http as order_period_http
from src.api.roles.domain import USER_PERMISSIONS, Actor, PermissionCode
from src.api.roles.infrastructure.auth import get_current_user
from src.api.roles.infrastructure import auth
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


def period_response(
    *,
    period_id: int = 7,
    status: OrderPeriodStatus = OrderPeriodStatus.OPEN,
) -> OrderPeriodResponse:
    opens_at = NOW - timedelta(days=1)
    closes_at = NOW + timedelta(days=14)

    if status is OrderPeriodStatus.DRAFT:
        opens_at = NOW + timedelta(days=1)
    elif status is OrderPeriodStatus.CLOSED:
        opens_at = NOW - timedelta(days=14)
        closes_at = NOW - timedelta(days=1)

    return OrderPeriodResponse(
        id=period_id,
        name="Pedido agosto 2026",
        opens_at=opens_at,
        closes_at=closes_at,
        created_by_user_id=ADMIN.user_id,
        date_added=NOW - timedelta(days=2),
        date_updated=None,
    )


def history_response() -> OrderPeriodHistoryResponse:
    return OrderPeriodHistoryResponse.model_validate(
        {
            "id": 1,
            "orderPeriodId": 7,
            "event": "created",
            "actorUserId": ADMIN.user_id,
            "occurredAt": NOW,
            "changes": [],
        }
    )


@pytest.mark.anyio
async def test_create_order_period_returns_201_and_public_schema(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)

    async def create(*args: object, **kwargs: object) -> object:
        return Ok(period_response())

    monkeypatch.setattr(order_period_http.order_period_cases, "create", create)

    response = await client.post(
        "/order-periods/",
        json={
            "name": "Pedido agosto 2026",
            "opensAt": NOW.isoformat(),
            "closesAt": (NOW + timedelta(days=14)).isoformat(),
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 7,
        "name": "Pedido agosto 2026",
        "opensAt": (NOW - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "closesAt": (NOW + timedelta(days=14)).isoformat().replace("+00:00", "Z"),
        "status": "open",
        "createdByUserId": 1,
        "dateAdded": (NOW - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
        "dateUpdated": None,
    }
    assert "password" not in response.text
    assert "session" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": 3, "opensAt": "tomorrow", "closesAt": []},
        {
            "name": "Pedido",
            "opensAt": "2026-08-02T12:00:00Z",
            "closesAt": "2026-08-01T12:00:00Z",
        },
        {
            "name": "Pedido",
            "opensAt": "2026-08-01T12:00:00",
            "closesAt": "2026-08-02T12:00:00",
        },
    ],
)
async def test_create_rejects_invalid_payloads(
    client: AsyncClient, payload: dict[str, object]
) -> None:
    authenticate(ADMIN)

    response = await client.post("/order-periods/", json=payload)

    assert response.status_code == 422


@pytest.mark.anyio
async def test_list_propagates_status_and_pagination(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)
    captured: dict[str, object] = {}

    async def get_multi(
        db: object,
        actor: Actor,
        *,
        page: int,
        shows: int,
        status: OrderPeriodStatus | None,
    ) -> object:
        captured.update(
            {"actor": actor, "page": page, "shows": shows, "status": status}
        )
        return Ok(([period_response()], 1))

    monkeypatch.setattr(order_period_http.order_period_cases, "get_multi", get_multi)

    response = await client.get(
        "/order-periods/", params={"page": 2, "shows": 25, "status": "open"}
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "open"
    assert captured == {
        "actor": ADMIN,
        "page": 2,
        "shows": 25,
        "status": OrderPeriodStatus.OPEN,
    }


@pytest.mark.anyio
async def test_regular_user_draft_filter_returns_an_empty_collection(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def get_multi(*args: object, **kwargs: object) -> object:
        assert args[1] == USER
        assert kwargs["status"] is OrderPeriodStatus.DRAFT
        return Ok(([], 0))

    monkeypatch.setattr(order_period_http.order_period_cases, "get_multi", get_multi)

    response = await client.get("/order-periods/?status=draft")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


@pytest.mark.anyio
async def test_list_rejects_unknown_status(client: AsyncClient) -> None:
    authenticate(USER)

    response = await client.get("/order-periods/?status=cancelled")

    assert response.status_code == 422


@pytest.mark.anyio
async def test_read_published_period_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def get_one(*args: object, **kwargs: object) -> object:
        return Ok(period_response())

    monkeypatch.setattr(order_period_http.order_period_cases, "get_one", get_one)

    response = await client.get("/order-periods/7")

    assert response.status_code == 200
    assert response.json()["id"] == 7


@pytest.mark.anyio
async def test_patch_order_period_returns_updated_resource(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)
    updated = period_response()
    updated.name = "Pedido extendido"

    async def update(*args: object, **kwargs: object) -> object:
        return Ok(updated)

    monkeypatch.setattr(order_period_http.order_period_cases, "update", update)

    response = await client.patch("/order-periods/7", json={"name": "Pedido extendido"})

    assert response.status_code == 200
    assert response.json()["name"] == "Pedido extendido"


@pytest.mark.anyio
async def test_close_order_period_returns_closed_resource(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)

    async def close(*args: object, **kwargs: object) -> object:
        return Ok(period_response(status=OrderPeriodStatus.CLOSED))

    monkeypatch.setattr(order_period_http.order_period_cases, "close", close)

    response = await client.post("/order-periods/7/close")

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/order-periods/7", "/order-periods/7/history"])
async def test_draft_and_its_history_are_hidden_from_regular_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    authenticate(USER)

    async def get_one(*args: object, **kwargs: object) -> object:
        return Ok(period_response(status=OrderPeriodStatus.DRAFT))

    async def get_history(*args: object, **kwargs: object) -> object:
        return Ok([history_response()])

    monkeypatch.setattr(order_period_http.order_period_cases, "get_one", get_one)
    monkeypatch.setattr(
        order_period_http.order_period_cases, "get_history", get_history
    )

    response = await client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "El Pedido no existe"}


@pytest.mark.anyio
async def test_admin_can_read_draft_history(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(ADMIN)

    async def get_one(*args: object, **kwargs: object) -> object:
        return Ok(period_response(status=OrderPeriodStatus.DRAFT))

    async def get_history(*args: object, **kwargs: object) -> object:
        return Ok([history_response()])

    monkeypatch.setattr(order_period_http.order_period_cases, "get_one", get_one)
    monkeypatch.setattr(
        order_period_http.order_period_cases, "get_history", get_history
    )

    response = await client.get("/order-periods/7/history")

    assert response.status_code == 200
    assert response.json()[0]["event"] == "created"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        (
            "POST",
            "/order-periods/",
            {
                "name": "Pedido",
                "opensAt": NOW.isoformat(),
                "closesAt": (NOW + timedelta(days=1)).isoformat(),
            },
        ),
        ("PATCH", "/order-periods/7", {"name": "Otro nombre"}),
        ("POST", "/order-periods/7/close", None),
    ],
)
async def test_regular_user_cannot_administer_periods(
    client: AsyncClient,
    method: str,
    path: str,
    json: dict[str, object] | None,
) -> None:
    authenticate(USER)

    response = await client.request(method, path, json=json)

    assert response.status_code == 403


@pytest.mark.anyio
async def test_protected_endpoint_requires_identity(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(auth.auth_settings, "mode", "disabled")
    monkeypatch.setattr(auth.auth_settings, "local_user_id", None)

    response = await client.get("/order-periods/")

    assert response.status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("case_result", "expected_status", "expected_detail"),
    [
        (Err(OrderPeriodNotFound(7)), 404, "El Pedido no existe"),
        (
            Err(OrderPeriodImmutableField("name")),
            409,
            "El Pedido no admite ese cambio en su estado actual",
        ),
        (
            Err(OrderPeriodDateConflict()),
            409,
            "Las fechas del Pedido entran en conflicto con su estado actual",
        ),
        (Err(OrderPeriodAlreadyClosed(7)), 409, "El Pedido ya está cerrado"),
    ],
)
async def test_patch_translates_every_recoverable_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    case_result: object,
    expected_status: int,
    expected_detail: str,
) -> None:
    authenticate(ADMIN)

    async def update(*args: object, **kwargs: object) -> object:
        return case_result

    monkeypatch.setattr(order_period_http.order_period_cases, "update", update)

    response = await client.patch("/order-periods/7", json={"name": "Nuevo"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("case_result", "expected_status", "expected_detail"),
    [
        (Err(OrderPeriodNotFound(7)), 404, "El Pedido no existe"),
        (Err(OrderPeriodAlreadyClosed(7)), 409, "El Pedido ya está cerrado"),
        (
            Err(OrderPeriodCannotCloseDraft(7)),
            409,
            "Un Pedido en borrador no se puede cerrar",
        ),
    ],
)
async def test_close_translates_every_recoverable_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    case_result: object,
    expected_status: int,
    expected_detail: str,
) -> None:
    authenticate(ADMIN)

    async def close(*args: object, **kwargs: object) -> object:
        return case_result

    monkeypatch.setattr(order_period_http.order_period_cases, "close", close)

    response = await client.post("/order-periods/7/close")

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


@pytest.mark.anyio
async def test_missing_period_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    authenticate(USER)

    async def get_one(*args: object, **kwargs: object) -> object:
        return Err(OrderPeriodNotFound(404))

    monkeypatch.setattr(order_period_http.order_period_cases, "get_one", get_one)

    response = await client.get("/order-periods/404")

    assert response.status_code == 404
    assert response.json() == {"detail": "El Pedido no existe"}


@pytest.mark.anyio
async def test_delete_route_does_not_exist(client: AsyncClient) -> None:
    authenticate(ADMIN)

    response = await client.delete("/order-periods/7")

    assert response.status_code == 405


def test_overrides_fixture_leaves_no_global_state() -> None:
    assert app.dependency_overrides == {}
