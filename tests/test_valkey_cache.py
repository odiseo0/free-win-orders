from collections.abc import AsyncIterator
from fnmatch import fnmatch

import pytest

from src.core.services.cache import ValkeyCache


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeValkeyClient:
    def __init__(self) -> None:
        self.data: dict[str, str | bytes] = {}
        self.expirations: dict[str, int | None] = {}
        self.delete_batches: list[tuple[str | bytes, ...]] = []
        self.pinged = False
        self.closed = False

    async def ping(self) -> bool:
        self.pinged = True
        return True

    async def get(self, key: str) -> str | bytes | None:
        return self.data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> bool:
        self.data[key] = value
        self.expirations[key] = ex
        return True

    async def delete(self, *keys: str | bytes) -> int:
        self.delete_batches.append(keys)

        for key in keys:
            normalized_key = key.decode() if isinstance(key, bytes) else key
            self.data.pop(normalized_key, None)

        return len(keys)

    async def scan_iter(
        self,
        *,
        match: str,
        count: int,
    ) -> AsyncIterator[str | bytes]:
        assert count == 100

        for key in list(self.data):
            if fnmatch(key, match):
                yield key

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_valkey_cache_applies_namespace_and_ttl() -> None:
    client = FakeValkeyClient()
    cache = ValkeyCache(client, key_prefix="free-win:test:")

    await cache.start()
    await cache.set("cards:item:1", "payload", ttl_seconds=300)

    assert client.pinged is True
    assert client.data["free-win:test:cards:item:1"] == "payload"
    assert client.expirations["free-win:test:cards:item:1"] == 300
    assert await cache.get("cards:item:1") == "payload"


@pytest.mark.anyio
async def test_valkey_cache_decodes_byte_responses() -> None:
    client = FakeValkeyClient()
    client.data["free-win:cards:item:1"] = b"payload"
    cache = ValkeyCache(client)

    assert await cache.get("cards:item:1") == "payload"


@pytest.mark.anyio
async def test_valkey_cache_deletes_prefix_with_scan_batches() -> None:
    client = FakeValkeyClient()
    client.data = {
        **{f"free-win:cards:list:{index}": "payload" for index in range(101)},
        "free-win:cards:item:1": "keep",
    }
    cache = ValkeyCache(client)

    await cache.delete_prefix("cards:list:")

    assert [len(batch) for batch in client.delete_batches] == [100, 1]
    assert client.data == {"free-win:cards:item:1": "keep"}


@pytest.mark.anyio
async def test_valkey_cache_closes_client_pool() -> None:
    client = FakeValkeyClient()
    cache = ValkeyCache(client)

    await cache.close()

    assert client.closed is True
