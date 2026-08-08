import asyncio
from typing import Any

from cachetools import TTLCache


class AsyncTTLCache:
    """Small process-local TTL cache safe for concurrent async requests."""

    def __init__(self, ttl_seconds: int) -> None:
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=512, ttl=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            return self._cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._cache[key] = value
