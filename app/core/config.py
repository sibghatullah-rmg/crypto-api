from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_version: str = "1.0.0"
    api_key: str = "change-me"
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_demo_api_key: str | None = None
    external_timeout_seconds: float = 10.0
    cache_ttl_seconds: int = 60
    webhook_url: str | None = None
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
