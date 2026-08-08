# Vetty Cryptocurrency API

A versioned REST API that proxies public CoinGecko cryptocurrency data. It uses asynchronous HTTP calls, validates inputs, applies an in-memory TTL cache, and emits a best-effort webhook for fresh market responses.

## Features

- Public health endpoint with application and upstream availability.
- API-key protected coin, category, and CAD market-data endpoints.
- Query pagination (`page_num`, `per_page`) on every collection endpoint.
- Configurable external timeout and cache TTL (60 seconds by default).
- Consistent JSON errors, centralized exception handling, structured JSON logs.
- OpenAPI documentation at `/docs` and `/openapi.json`.
- Unit tests that mock CoinGecko; no live API calls are made during tests.

## Quick start

Requires Python 3.10+.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The local API key is `change-me` until you replace it in `.env`. In a deployed environment, always supply a high-entropy `API_KEY` environment variable.

## API

| Method | Endpoint | Authentication | Description |
| --- | --- | --- | --- |
| GET | `/health` | No | Application version and CoinGecko reachability |
| GET | `/api/v1/coins` | `X-API-Key` | Available coins |
| GET | `/api/v1/categories` | `X-API-Key` | Available categories |
| GET | `/api/v1/market-data` | `X-API-Key` | CAD market data |

Every collection endpoint accepts `page_num` (default `1`) and `per_page` (default `10`, maximum `250`). Market data requires at least one of `coin_id` or `category`; when both are supplied, both are sent to CoinGecko for intersection filtering.

```bash
curl http://localhost:8000/health
curl -H 'X-API-Key: change-me' 'http://localhost:8000/api/v1/coins?page_num=1&per_page=10'
curl -H 'X-API-Key: change-me' 'http://localhost:8000/api/v1/market-data?coin_id=bitcoin'
curl -H 'X-API-Key: change-me' 'http://localhost:8000/api/v1/market-data?category=layer-1'
```

Successful error responses are deliberately shaped consistently:

```json
{"error":{"code":"validation_error","message":"Invalid request parameters","details":[]}}
```

External service timeouts return `504`; upstream errors return `502`. Authentication failures return `401`, invalid query input `422`, and a missing market filter `400`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_KEY` | `change-me` | Required `X-API-Key` value |
| `APP_VERSION` | `1.0.0` | Reported API version |
| `COINGECKO_BASE_URL` | Public CoinGecko v3 URL | External API base URL |
| `COINGECKO_DEMO_API_KEY` | unset | CoinGecko Demo API key, sent as `x-cg-demo-api-key` |
| `EXTERNAL_TIMEOUT_SECONDS` | `10` | HTTP client timeout |
| `CACHE_TTL_SECONDS` | `60` | Process-local response cache duration |
| `WEBHOOK_URL` | unset | Optional notification destination |
| `LOG_LEVEL` | `INFO` | Structured log verbosity |

When `WEBHOOK_URL` is configured, a GET request is sent after every successful non-cached CoinGecko request made by the collection endpoints. Its query parameters include an `event` such as `coins.retrieved`, `categories.retrieved`, or `market_data.retrieved`, plus `records_count`. Webhook delivery is best effort and never changes a successful client response; check the structured logs for `webhook_delivered`, `webhook_skipped`, or `webhook_delivery_failed`.

## Quality checks and Docker

```bash
make lint
make test
docker compose up --build
```

Or run `docker build -t vetty-api .` followed by `docker run --env-file .env -p 8000:8000 vetty-api`.

## Design notes

The cache is intentionally process-local, as requested. For multi-replica production deployment, replace it with a shared cache such as Redis to retain cache coherence. CoinGecko's `/ping` response does not reliably publish a service version; the API reports it when upstream supplies one, otherwise `null`. 
