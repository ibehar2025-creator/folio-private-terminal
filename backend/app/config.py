from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/folio.db"
    environment: Literal["development", "production"] = "development"
    app_origin: str = "http://127.0.0.1:5173"
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    session_hours: int = Field(default=12, ge=1, le=168)
    demo_mode: bool = False
    google_application_credentials: str = ""
    google_sheet_id: str = ""
    google_folder_id: str = ""
    market_provider: Literal["disabled", "finnhub"] = "disabled"
    market_api_key: str = ""
    market_requests_per_minute: int = Field(default=6, ge=1, le=600)
    history_provider: Literal["yahoo", "market"] = "yahoo"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    sync_interval_minutes: int = Field(default=15, ge=1, le=1440)
    risk_free_rate: float = Field(default=0.04, ge=-1, le=1)

    @property
    def secure_cookies(self):
        return self.environment == "production"

    @property
    def history_source(self):
        if self.demo_mode:
            return "demo"
        return (
            self.market_provider
            if self.history_provider == "market"
            else self.history_provider
        )


@lru_cache
def get_settings():
    settings = Settings()
    if settings.environment == "production":
        if not settings.database_url.startswith(
            "postgresql"
        ) or not settings.app_origin.startswith("https://"):
            raise RuntimeError("Production requires PostgreSQL and an HTTPS APP_ORIGIN")
        if settings.demo_mode:
            raise RuntimeError("DEMO_MODE must be disabled in production")
    return settings
