from .base import Cache
from .memory import InMemoryCache

_cache: Cache = InMemoryCache()


def get_cache() -> Cache:
    return _cache
