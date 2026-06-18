import json
from datetime import datetime, UTC, timedelta
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from prisma import Prisma

logger = get_logger(__name__)

REFRESH_BUFFER_SECONDS = 300  # refresh 5 minutes before expiry


async def get_valid_token(integration_id: str, db: "Prisma") -> str:
    """
    Returns a valid access_token for the integration, refreshing if within
    REFRESH_BUFFER_SECONDS of expiry. All integrations must call this — never
    access stored tokens directly.
    """
    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        raise ValueError(f"Integration not found: {integration_id}")

    creds = json.loads(integration.encrypted_credentials)

    expiry_str = creds.get("token_expiry_at")
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str)
        if datetime.now(UTC) >= expiry - timedelta(seconds=REFRESH_BUFFER_SECONDS):
            creds = await _refresh_and_store(integration, creds, db)

    token = creds.get("access_token", "")
    if not token:
        raise ValueError(f"No access_token found for integration {integration_id}")
    return token


async def _refresh_and_store(integration, creds: dict, db: "Prisma") -> dict:
    """Calls the correct refresh function for the integration type, stores result."""
    integration_type = integration.type

    try:
        new_tokens = await _call_refresh(integration_type, creds)
    except Exception as exc:
        logger.error(
            "Token refresh failed for %s/%s: %s",
            integration_type,
            integration.id,
            type(exc).__name__,
        )
        raise

    updated = {**creds, **new_tokens}
    await db.integration.update(
        where={"id": integration.id},
        data={"encrypted_credentials": json.dumps(updated)},
    )
    logger.info("Token refreshed for integration %s/%s", integration_type, integration.id)
    return updated


async def _call_refresh(integration_type: str, creds: dict) -> dict:
    """Dispatches to the correct refresh implementation. Lazy imports to avoid circular deps."""
    refresh_token = creds.get("refresh_token", "")
    if not refresh_token:
        raise ValueError(f"No refresh_token stored for {integration_type}")

    if integration_type == "xero":
        from app.integrations.xero.client import refresh_xero_token
        return await refresh_xero_token(refresh_token)

    if integration_type == "truelayer":
        from app.integrations.truelayer.client import refresh_truelayer_token
        return await refresh_truelayer_token(refresh_token)

    if integration_type == "hubspot":
        from app.integrations.hubspot.client import refresh_hubspot_token
        return await refresh_hubspot_token(refresh_token)

    if integration_type in ("gmail", "google_drive"):
        from app.integrations.google.client import refresh_google_token
        return await refresh_google_token(refresh_token)

    if integration_type == "outlook":
        from app.integrations.outlook.client import refresh_outlook_token
        return await refresh_outlook_token(refresh_token)

    if integration_type == "salesforce":
        from app.integrations.salesforce.client import refresh_sf_token
        return await refresh_sf_token(refresh_token)

    if integration_type == "stripe":
        # Stripe Connect tokens don't expire — no refresh needed
        raise ValueError("Stripe Connect tokens do not expire")

    raise ValueError(f"No refresh handler registered for integration type: {integration_type!r}")
