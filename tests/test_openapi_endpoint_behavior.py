from collections.abc import AsyncIterator, Generator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.roles.domain import Actor, PermissionCode
from src.api.roles.infrastructure.auth import get_current_user
from src.api.users.infrastructure import users_api
from src.application import app
from src.core import Ok
from src.core.db import get_db

ADMIN = Actor(user_id=1, permissions=frozenset(PermissionCode))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def override_boundaries() -> Generator[None]:
    async def fake_db() -> AsyncIterator[object]:
        yield object()

    async def fake_actor() -> Actor:
        return ADMIN

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = fake_actor
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_users_endpoint_returns_the_published_paginated_shape(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, int] = {}

    async def get_multi(
        db: object, *, page: int, shows: int
    ) -> object:
        captured.update(page=page, shows=shows)
        return Ok(
            (
                [
                    {
                        "id": 7,
                        "firstName": "Yugi",
                        "lastName": "Muto",
                        "email": "yugi@example.test",
                    }
                ],
                1,
            )
        )

    monkeypatch.setattr(users_api, "get_multi", get_multi)

    response = await client.get("/users/", params={"page": 2, "shows": 25})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "externalId": None,
                "firstName": "Yugi",
                "lastName": "Muto",
                "alias": None,
                "email": "yugi@example.test",
                "phoneNumber": None,
                "phoneCode": None,
                "idNumber": None,
                "id": 7,
            }
        ],
        "total": 1,
    }
    assert captured == {"page": 2, "shows": 25}


@pytest.mark.anyio
async def test_user_delete_returns_204_with_an_empty_body(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def remove(db: object, *, user_id: int) -> object:
        assert user_id == 7
        return Ok(None)

    monkeypatch.setattr(users_api, "remove", remove)

    response = await client.delete("/users/7")

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.anyio
async def test_normalized_query_and_path_limits_are_enforced(
    client: AsyncClient,
) -> None:
    assert (await client.get("/users/", params={"page": 0})).status_code == 422
    assert (await client.get("/users/", params={"shows": 101})).status_code == 422
    assert (await client.delete("/users/0")).status_code == 422
