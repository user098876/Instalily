import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/instalily"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_api_base: str = "http://localhost:8000/api"

    openai_api_key: str | None = None
    clearbit_api_key: str | None = None
    apollo_api_key: str | None = None
    clay_api_key: str | None = None
    peopledatalabs_api_key: str | None = None
    serp_api_key: str | None = None

    enable_linkedin_sales_nav: bool = False
    request_timeout_seconds: int = 20
    max_retries: int = 3

    demo_fixture_mode: bool = False
    demo_fixture_manifest: str = "data/demo_fixtures/manifest.json"
    max_roster_links_per_parent: int = 8
    max_stakeholder_pages: int = 6

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_cors_origins(cls, value: object) -> str:
        if isinstance(value, (list, tuple)):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if value is None:
            return ""
        return str(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @field_validator("database_url", "redis_url", "frontend_api_base")
    @classmethod
    def _ensure_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        raw_value = self.cors_origins.strip()
        defaults = ["http://localhost:5173", "http://127.0.0.1:5173"]
        if not raw_value:
            return defaults
        if raw_value.startswith("["):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                origins = [str(item).strip() for item in parsed if str(item).strip()]
                if origins:
                    return origins
        origins = [item.strip() for item in raw_value.split(",") if item.strip()]
        return origins or defaults


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
