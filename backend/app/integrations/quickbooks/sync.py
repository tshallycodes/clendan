"""
QuickBooks sync job — runs via arq worker.
Fetches company info and validates connection. Full invoice/account sync added in Phase 4+.
"""
import json
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.quickbooks import client as qb

logger = get_logger(__name__)


async def sync_quickbooks_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: verify QuickBooks connection is live, refresh token if needed.
    Returns sync result dict.
    """
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        logger.warning("Sync skipped — integration %s not connected", integration_id)
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on sync job — possible data leakage attempt blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = json.loads(integration.encrypted_credentials)
        realm_id = creds.get("realm_id", "")

        # Verify connection is live
        company = await qb.get_company_info(
            encrypted_access=creds["access_token"],
            realm_id=realm_id,
            sandbox=settings.quickbooks_sandbox,
        )
        await db.integration.update(
            where={"id": integration_id},
            data={"last_synced_at": datetime.now(UTC)},
        )
        logger.info("QB sync OK: tenant=%s company=%s", tenant_id, company.get("company_name"))
        return {"status": "ok", "company": company}

    except Exception as exc:
        logger.error("QB sync failed for integration %s: %s", integration_id, type(exc).__name__)

        # Attempt token refresh
        try:
            creds = json.loads(integration.encrypted_credentials)
            new_tokens = await qb.refresh_token(creds["refresh_token"])
            updated_creds = {**creds, **new_tokens}
            await db.integration.update(
                where={"id": integration_id},
                data={"encrypted_credentials": json.dumps(updated_creds)},
            )
            logger.info("QB token refreshed for integration %s", integration_id)
            return {"status": "token_refreshed"}
        except Exception as refresh_exc:
            logger.error("QB token refresh also failed: %s", type(refresh_exc).__name__)
            await db.integration.update(
                where={"id": integration_id},
                data={"status": "error"},
            )
            return {"status": "error", "reason": str(type(refresh_exc).__name__)}


async def enqueue_quickbooks_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a QuickBooks sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_quickbooks_connection", integration_id, tenant_id)
    await redis.aclose()
