"""
QuickBooks sync job — runs via arq tool.
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

    import time as _time
    start = _time.monotonic()
    sync_status = "success"
    records = 0

    try:
        creds = json.loads(integration.encrypted_credentials)
        realm_id = creds.get("realm_id", "")

        # Attempt token refresh if access token may be stale
        try:
            new_tokens = await qb.refresh_token(creds["refresh_token"])
            updated_creds = {**creds, **new_tokens}
            await db.integration.update(
                where={"id": integration_id},
                data={"encrypted_credentials": json.dumps(updated_creds)},
            )
            creds = updated_creds
            logger.info("QB token refreshed for integration %s", integration_id)
        except Exception:
            pass  # use existing token — may still be valid

        company = await qb.get_company_info(
            encrypted_access=creds["access_token"],
            realm_id=realm_id,
            sandbox=settings.quickbooks_sandbox,
        )
        records = 1  # company record fetched
        logger.info("QB sync OK: tenant=%s company=%s", tenant_id, company.get("company_name"))

    except Exception as exc:
        logger.error("QB sync failed for integration %s: %s", integration_id, type(exc).__name__)
        sync_status = "error"

    elapsed = int((_time.monotonic() - start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration.id,
        "entity_type": "company",
        "status": sync_status,
        "records_synced": records,
        "duration_ms": elapsed,
    })

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.warning("Sync skipped — integration %s was disconnected during run", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    if sync_status == "success":
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "last_synced_at": datetime.now(UTC)},
        )
        return {"status": "ok"}
    else:
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "sync_failed"}


async def enqueue_quickbooks_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a QuickBooks sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_quickbooks_connection", integration_id, tenant_id)
    await redis.aclose()
