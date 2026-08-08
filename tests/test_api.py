import httpx
import pytest
from app.main import app, settings
from app.services.coingecko import CoinGeckoClient
from httpx import ASGITransport, AsyncClient, MockTransport, Response


class WebhookSpy:
    def __init__(self) -> None:
        self.calls = 0

    async def notify_external_data(self, event: str, records_count: int) -> None:
        self.calls += 1


AUTH_HEADERS = {"X-API-Key": settings.api_key}


@pytest.fixture
async def api_client():
    calls: list[str] = []

    def handler(request: httpx.Request) -> Response:
        calls.append(str(request.url))
        if request.url.path.endswith("/ping"):
            return Response(200, json={"gecko_says": "(V3) To the Moon!"})
        if request.url.path.endswith("/coins/list"):
            return Response(
                200,
                json=[
                    {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc"},
                    {"id": "ethereum", "name": "Ethereum", "symbol": "eth"},
                ],
            )
        if request.url.path.endswith("/coins/categories/list"):
            return Response(200, json=[{"category_id": "layer-1", "name": "Layer 1"}])
        if request.url.path.endswith("/coins/markets"):
            return Response(
                200,
                json=[
                    {
                        "id": "bitcoin",
                        "name": "Bitcoin",
                        "symbol": "btc",
                        "current_price": 100000.0,
                        "market_cap": 2000000.0,
                        "market_cap_rank": 1,
                        "total_volume": 50000.0,
                        "price_change_percentage_24h": 2.5,
                        "last_updated": "2026-01-01T00:00:00.000Z",
                    }
                ],
            )
        return Response(404)

    service = CoinGeckoClient("https://example.test/api/v3", 1, 60)
    await service.client.aclose()
    service.client = AsyncClient(
        base_url="https://example.test/api/v3", transport=MockTransport(handler), timeout=1
    )
    app.state.coingecko = service
    app.state.webhook = WebhookSpy()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, calls, app.state.webhook
    await service.close()


@pytest.mark.asyncio
async def test_health_is_public_and_reports_external_status(api_client):
    client, _, _ = api_client
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["external_service"] == "reachable"


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_missing_key(api_client):
    client, _, _ = api_client
    response = await client.get("/api/v1/coins")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_coins_are_paginated(api_client):
    client, _, webhook = api_client
    response = await client.get("/api/v1/coins?per_page=1", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 2
    assert payload["items"] == [{"id": "bitcoin", "name": "Bitcoin", "symbol": "btc"}]
    assert webhook.calls == 1


@pytest.mark.asyncio
async def test_market_requires_a_filter(api_client):
    client, _, _ = api_client
    response = await client.get("/api/v1/market-data", headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "coin_id or category is required"


@pytest.mark.asyncio
async def test_market_uses_cad_and_notifies_only_on_cache_miss(api_client):
    client, calls, webhook = api_client
    response = await client.get("/api/v1/market-data?coin_id=bitcoin", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["items"][0]["current_price_cad"] == 100000.0
    assert webhook.calls == 1
    await client.get("/api/v1/market-data?coin_id=bitcoin", headers=AUTH_HEADERS)
    assert webhook.calls == 1
    assert sum("/coins/markets" in url for url in calls) == 1


@pytest.mark.asyncio
async def test_coingecko_demo_key_is_sent_as_upstream_header():
    service = CoinGeckoClient("https://example.test/api/v3", 1, 60, demo_api_key="demo-secret")
    assert service.client.headers["x-cg-demo-api-key"] == "demo-secret"
    await service.close()
