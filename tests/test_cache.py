import pytest

from src.core.services.cache import InMemoryCache


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_in_memory_cache_deletes_only_matching_prefix() -> None:
    cache = InMemoryCache()
    await cache.set("orders:item:1", "one")
    await cache.set("orders:list:1:100", "many")
    await cache.set("order-periods:item:1", "period")

    await cache.delete_prefix("orders:")

    assert await cache.get("orders:item:1") is None
    assert await cache.get("orders:list:1:100") is None
    assert await cache.get("order-periods:item:1") == "period"
