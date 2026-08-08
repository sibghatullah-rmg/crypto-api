import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.core.errors import (
    ExternalServiceError,
    external_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.schemas import Category, Coin, HealthResponse, MarketData
from app.services.coingecko import CoinGeckoClient
from app.services.webhook import WebhookNotifier

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.coingecko = CoinGeckoClient(
        settings.coingecko_base_url,
        settings.external_timeout_seconds,
        settings.cache_ttl_seconds,
        settings.coingecko_demo_api_key,
    )
    app.state.webhook = WebhookNotifier(settings.webhook_url, settings.external_timeout_seconds)
    yield
    await app.state.coingecko.close()


app = FastAPI(
    title="Vetty Cryptocurrency API",
    version=settings.app_version,
    description="Authenticated API proxy for Canadian-dollar cryptocurrency market data.",
    lifespan=lifespan,
)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ExternalServiceError, external_exception_handler)


async def get_pagination(
    page_num: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=250)] = 10,
) -> PaginationParams:
    return PaginationParams(page_num=page_num, per_page=per_page)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


async def get_coingecko(request: Request) -> CoinGeckoClient:
    return request.app.state.coingecko


async def get_webhook(request: Request) -> WebhookNotifier:
    return request.app.state.webhook


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(
    client: CoinGeckoClient = Depends(get_coingecko),  # noqa: B008
) -> HealthResponse:
    external_status, external_version = await client.health()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        external_service=external_status,
        external_service_version=external_version,
    )


@app.get(
    "/api/v1/coins",
    response_model=PaginatedResponse[Coin],
    dependencies=[Depends(require_api_key)],
    tags=["coins"],
)
async def list_coins(
    pagination: Pagination,
    client: CoinGeckoClient = Depends(get_coingecko),  # noqa: B008
    webhook: WebhookNotifier = Depends(get_webhook),  # noqa: B008
) -> PaginatedResponse[Coin]:
    result = await client.coins()
    if not result.from_cache:
        await webhook.notify_external_data("coins.retrieved", len(result.data))
    coins = [Coin.model_validate(item) for item in result.data]
    return paginate(coins, pagination)


@app.get(
    "/api/v1/categories",
    response_model=PaginatedResponse[Category],
    dependencies=[Depends(require_api_key)],
    tags=["categories"],
)
async def list_categories(
    pagination: Pagination,
    client: CoinGeckoClient = Depends(get_coingecko),  # noqa: B008
    webhook: WebhookNotifier = Depends(get_webhook),  # noqa: B008
) -> PaginatedResponse[Category]:
    result = await client.categories()
    if not result.from_cache:
        await webhook.notify_external_data("categories.retrieved", len(result.data))
    categories = [
        Category(category_id=item["category_id"], name=item["name"]) for item in result.data
    ]
    return paginate(categories, pagination)


@app.get(
    "/api/v1/market-data",
    response_model=PaginatedResponse[MarketData],
    dependencies=[Depends(require_api_key)],
    tags=["market data"],
)
async def market_data(
    pagination: Pagination,
    coin_id: Annotated[str | None, Query(min_length=1)] = None,
    category: Annotated[str | None, Query(min_length=1)] = None,
    client: CoinGeckoClient = Depends(get_coingecko),  # noqa: B008
    webhook: WebhookNotifier = Depends(get_webhook),  # noqa: B008
) -> PaginatedResponse[MarketData]:
    if not coin_id and not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="coin_id or category is required",
        )

    result = await client.markets(coin_id, category)
    if not result.from_cache:
        await webhook.notify_external_data("market_data.retrieved", len(result.data))
    records = [
        MarketData(
            coin_id=item["id"],
            name=item["name"],
            symbol=item["symbol"],
            current_price_cad=item.get("current_price"),
            market_cap_cad=item.get("market_cap"),
            market_cap_rank=item.get("market_cap_rank"),
            total_volume_cad=item.get("total_volume"),
            price_change_percentage_24h=item.get("price_change_percentage_24h"),
            last_updated=item.get("last_updated"),
            category=category,
        )
        for item in result.data
    ]
    return paginate(records, pagination)
