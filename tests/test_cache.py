import pytest

from src.core.services.cache import InMemoryCache


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_in_memory_cache_deletes_only_matching_prefix() -> None:
    cache = InMemoryCache()
    await cache.set("cards:item:1", "one")
    await cache.set("cards:list:1:100", "many")
    await cache.set("card-listings:item:1", "listing")

    await cache.delete_prefix("cards:")

    assert await cache.get("cards:item:1") is None
    assert await cache.get("cards:list:1:100") is None
    assert await cache.get("card-listings:item:1") == "listing"
