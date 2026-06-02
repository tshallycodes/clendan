from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "Clendan"
    environment: str = "development"
    debug: bool = False

    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_frontend_api: str = ""

    anthropic_api_key: str = ""

    sentry_dsn: str = ""
    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"

    encryption_key: str = ""

    max_agent_attempts: int = 3
    backoff_seconds: float = 1.0
    approval_ttl_seconds: int = 86400


@lru_cache()
def get_settings() -> Settings:
    return Settings()
