import os
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "Clendan"
    environment: str = "development"
    debug: bool = False

    database_url: str = ""
    redis_public_url: str = "redis://localhost:6379/0"

    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_frontend_api: str = ""

    anthropic_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"

    sentry_dsn: str = ""
    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"

    encryption_key: str = ""

    max_agent_attempts: int = 3
    backoff_seconds: float = 1.0
    approval_ttl_seconds: int = 86400

    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_redirect_uri: str = ""
    quickbooks_sandbox: bool = True
    quickbooks_webhook_verifier_token: str = ""
    quickbooks_default_account_id: str = ""  # optional override; falls back to querying first Expense account

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox | development | production
    plaid_webhook_secret: str = ""

    stripe_webhook_secret: str = ""
    stripe_client_id: str = ""
    stripe_secret_key: str = ""
    stripe_redirect_uri: str = ""

    # SaaS billing (Clendan's own subscriptions) - separate webhook endpoint + secret from Connect
    stripe_billing_webhook_secret: str = ""
    stripe_price_starter: str = ""  # Stripe recurring Price ID for the Starter plan
    stripe_price_growth: str = ""   # Stripe recurring Price ID for the Growth plan

    xero_client_id: str = ""
    xero_client_secret: str = ""
    xero_redirect_uri: str = ""
    xero_webhook_key: str = ""

    truelayer_client_id: str = ""
    truelayer_client_secret: str = ""
    truelayer_redirect_uri: str = ""
    truelayer_env: str = "sandbox"  # sandbox | production

    mono_secret_key: str = ""
    mono_app_id: str = ""
    mono_webhook_secret: str = ""

    codat_api_key: str = ""
    codat_webhook_secret: str = ""

    gocardless_webhook_secret: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri_gmail: str = ""
    google_redirect_uri_drive: str = ""
    google_pubsub_topic: str = ""

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = ""
    microsoft_tenant_id: str = "common"

    integration_master_secret: str = ""

    square_client_id: str = ""
    square_client_secret: str = ""
    square_redirect_uri: str = ""
    square_webhook_signature_key: str = ""

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_redirect_uri: str = ""
    paypal_webhook_id: str = ""
    paypal_env: str = "sandbox"  # sandbox | live

    backend_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = ""  # comma-separated list of extra allowed origins

    freshbooks_client_id: str = ""
    freshbooks_client_secret: str = ""
    freshbooks_redirect_uri: str = ""

    sage_client_id: str = ""
    sage_client_secret: str = ""
    sage_redirect_uri: str = ""

    wave_client_id: str = ""
    wave_client_secret: str = ""

    wise_client_id: str = ""
    wise_client_secret: str = ""

    dropbox_client_id: str = ""
    dropbox_client_secret: str = ""
    dropbox_redirect_uri: str = ""

    onedrive_redirect_uri: str = ""

    netsuite_client_id: str = ""
    netsuite_client_secret: str = ""
    netsuite_redirect_uri: str = ""
    netsuite_account_id: str = ""

    dynamics_redirect_uri: str = ""

    sap_client_id: str = ""
    sap_client_secret: str = ""
    sap_token_url: str = ""
    sap_api_base_url: str = ""

    freshbooks_webhook_secret: str = ""
    adyen_webhook_hmac_key: str = ""
    wise_webhook_secret: str = ""
    sage_webhook_secret: str = ""
    truelayer_webhook_secret: str = ""

    exchange_rates_api_key: str = ""  # exchangerate-api.com v6 key - free tier (1,500 req/month)

    @model_validator(mode="after")
    def _compute_redirect_uris(self) -> "Settings":
        base = self.backend_base_url.rstrip("/")
        defaults = {
            "quickbooks_redirect_uri": f"{base}/integrations/quickbooks/callback",
            "xero_redirect_uri": f"{base}/integrations/xero/callback",
            "truelayer_redirect_uri": f"{base}/integrations/truelayer/callback",
            "google_redirect_uri_gmail": f"{base}/integrations/gmail/callback",
            "google_redirect_uri_drive": f"{base}/integrations/google-drive/callback",
            "microsoft_redirect_uri": f"{base}/integrations/outlook/callback",
            "square_redirect_uri": f"{base}/integrations/square/callback",
            "paypal_redirect_uri": f"{base}/integrations/paypal/callback",
            "freshbooks_redirect_uri": f"{base}/integrations/freshbooks/callback",
            "sage_redirect_uri": f"{base}/integrations/sage/callback",
            "dropbox_redirect_uri": f"{self.frontend_url.rstrip('/')}/auth/dropbox/callback",
            "onedrive_redirect_uri": f"{base}/integrations/onedrive/callback",
            "netsuite_redirect_uri": f"{base}/integrations/netsuite/callback",
            "dynamics_redirect_uri": f"{base}/integrations/dynamics/callback",
            "stripe_redirect_uri": f"{base}/integrations/stripe/callback",
        }
        for field, value in defaults.items():
            if not getattr(self, field):
                setattr(self, field, value)
        return self


@lru_cache()
def get_settings() -> Settings:
    overrides: dict = {}
    for env_var, field in [
        ("FRONTEND_URL", "frontend_url"),
        ("BACKEND_BASE_URL", "backend_base_url"),
    ]:
        val = os.environ.get(env_var, "").strip()
        if val:
            overrides[field] = val
    return Settings(**overrides)
