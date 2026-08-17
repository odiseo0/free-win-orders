from collections.abc import AsyncIterator, Generator

import pytest
from httpx import ASGITransport, AsyncClient

from src.application import app
from src.core.db import get_db
from src.core.services.cache import get_cache


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


class FakeDB:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.executed = False

    async def execute(self, _: object) -> None:
        self.executed = True

        if self.error is not None:
            raise self.error


class FakeCache:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.checked = False

    async def check_health(self) -> None:
        self.checked = True

        if self.error is not None:
            raise self.error


async def request(path: str) -> tuple[int, dict[str, str]]:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path)

    return response.status_code, response.json()


@pytest.mark.anyio
async def test_liveness_does_not_check_external_dependencies() -> None:
    async def fail_db() -> AsyncIterator[None]:
        raise AssertionError("Liveness must not request a database session")
        yield

    def fail_cache() -> None:
        raise AssertionError("Liveness must not request a cache")

    app.dependency_overrides[get_db] = fail_db
    app.dependency_overrides[get_cache] = fail_cache

    status_code, body = await request("/health/live")

    assert status_code == 200
    assert body == {"status": "ok"}


@pytest.mark.anyio
async def test_readiness_checks_database_and_cache() -> None:
    db = FakeDB()
    cache = FakeCache()

    async def override_db() -> AsyncIterator[FakeDB]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cache] = lambda: cache

    status_code, body = await request("/health/ready")

    assert status_code == 200
    assert body == {"status": "ready"}
    assert db.executed is True
    assert cache.checked is True


@pytest.mark.anyio
async def test_readiness_returns_503_when_database_is_unavailable() -> None:
    db = FakeDB(ConnectionError("database details must not be exposed"))
    cache = FakeCache()

    async def override_db() -> AsyncIterator[FakeDB]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cache] = lambda: cache

    status_code, body = await request("/health/ready")

    assert status_code == 503
    assert body == {"status": "unavailable"}
    assert cache.checked is False


@pytest.mark.anyio
async def test_readiness_returns_503_when_cache_is_unavailable() -> None:
    db = FakeDB()
    cache = FakeCache(ConnectionError("cache details must not be exposed"))

    async def override_db() -> AsyncIterator[FakeDB]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_cache] = lambda: cache

    status_code, body = await request("/health/ready")

    assert status_code == 503
    assert body == {"status": "unavailable"}
    assert db.executed is True
    assert cache.checked is True


def test_health_operation_ids_are_explicit() -> None:
    schema = app.openapi()

    assert schema["paths"]["/health/live"]["get"]["operationId"] == (
        "getHealthLiveness"
    )
    assert schema["paths"]["/health/ready"]["get"]["operationId"] == (
        "getHealthReadiness"
    )
