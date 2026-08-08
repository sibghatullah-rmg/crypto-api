from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    external_service: str
    external_service_version: str | None = None


class Coin(BaseModel):
    id: str
    name: str
    symbol: str


class Category(BaseModel):
    category_id: str
    name: str


class MarketData(BaseModel):
    coin_id: str
    name: str
    symbol: str
    current_price_cad: float | None = None
    market_cap_cad: float | None = None
    market_cap_rank: int | None = None
    total_volume_cad: float | None = None
    price_change_percentage_24h: float | None = None
    last_updated: str | None = None
    category: str | None = None
    raw: dict[str, Any] | None = None
