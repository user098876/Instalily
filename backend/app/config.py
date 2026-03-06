from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/instalily"
    redis_url: str = "redis://localhost:6379/0"

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
