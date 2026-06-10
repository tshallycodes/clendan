from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "Clendan"
    environment: str = "development"
    debug: bool = False

    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_frontend_api: str = ""

    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"

    sentry_dsn: str = ""
    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"

    encryption_key: str = ""

    max_agent_attempts: int = 3
    backoff_seconds: float = 1.0
    approval_ttl_seconds: int = 86400

    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_redirect_uri: str = "http://localhost:8000/v1/integrations/quickbooks/callback"
    quickbooks_sandbox: bool = True
    quickbooks_webhook_verifier_token: str = ""

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox | development | production
    plaid_webhook_secret: str = ""

    stripe_webhook_secret: str = ""
    stripe_client_id: str = ""
    stripe_secret_key: str = ""

    xero_client_id: str = ""
    xero_client_secret: str = ""
    xero_redirect_uri: str = "http://localhost:8000/v1/integrations/xero/callback"
    xero_webhook_key: str = ""

    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = "http://localhost:8000/v1/integrations/truelayer/callback"

    codat_api_key: str = ""

    gocardless_webhook_secret: str = ""

    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = "http://localhost:8000/v1/integrations/hubspot/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri_gmail: str = "http://localhost:8000/v1/integrations/gmail/callback"
    google_redirect_uri_drive: str = "http://localhost:8000/v1/integrations/google-drive/callback"
    google_pubsub_topic: str = ""

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/v1/integrations/outlook/callback"
    microsoft_tenant_id: str = "common"

    integration_master_secret: str = ""

    backend_base_url: str = "http://localhost:8000"

    freshbooks_client_id: str = ""
    freshbooks_client_secret: str = ""

    sage_client_id: str = ""
    sage_client_secret: str = ""

    wave_client_id: str = ""
    wave_client_secret: str = ""

    wise_client_id: str = ""
    wise_client_secret: str = ""

    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""

    dropbox_client_id: str = ""
    dropbox_client_secret: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
