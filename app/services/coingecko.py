import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import ExternalServiceError
from app.services.cache import AsyncTTLCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedResult:
    data: list[dict[str, Any]]
    from_cache: bool


class CoinGeckoClient:
    """Async client for the subset of CoinGecko endpoints used by this API."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        cache_ttl: int,
        demo_api_key: str | None = None,
    ) -> None:
        headers = {"x-cg-demo-api-key": demo_api_key} if demo_api_key else None
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers
        )
        self.cache = AsyncTTLCache(cache_ttl)

    async def close(self) -> None:
        await self.client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self.client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("Cryptocurrency service request timed out", 504) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "external_service_http_error", extra={"status": exc.response.status_code}
            )
            raise ExternalServiceError("Cryptocurrency service returned an error", 502) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalServiceError("Cryptocurrency service is unavailable", 502) from exc

    @staticmethod
    def _key(path: str, params: dict[str, Any] | None) -> str:
        return f"{path}:{sorted((params or {}).items())}"

    async def _cached_get(self, path: str, params: dict[str, Any] | None = None) -> CachedResult:
        key = self._key(path, params)
        cached = await self.cache.get(key)
        if cached is not None:
            return CachedResult(cached, True)
        data = await self._get(path, params)
        if not isinstance(data, list):
            raise ExternalServiceError("Cryptocurrency service returned an invalid response")
        await self.cache.set(key, data)
        return CachedResult(data, False)

    async def health(self) -> tuple[str, str | None]:
        try:
            payload = await self._get("/ping")
            version = payload.get("version") if isinstance(payload, dict) else None
            return "reachable", version
        except ExternalServiceError:
            return "unreachable", None

    async def coins(self) -> CachedResult:
        return await self._cached_get("/coins/list")

    async def categories(self) -> CachedResult:
        return await self._cached_get("/coins/categories/list")

    async def markets(self, coin_id: str | None, category: str | None) -> CachedResult:
        params: dict[str, Any] = {
            "vs_currency": "cad",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
        }
        if coin_id:
            params["ids"] = coin_id
        if category:
            params["category"] = category
        return await self._cached_get("/coins/markets", params)
