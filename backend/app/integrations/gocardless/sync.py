"""
GoCardless sync job — runs via arq tool.
Fetches mandates, payments, and payouts for a connected GoCardless integration.
Writes sync log entries per entity type.
"""
import time

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.gocardless import client as gc

logger = get_logger(__name__)


async def sync_gocardless_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches mandates, payments, and payouts for a GoCardless integration.
    Writes a sync log entry for each entity type.
    Zero trust: validates all data from GoCardless before writing.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("connected", "syncing"):
        logger.warning("GoCardless sync skipped — integration %s not in syncable state", integration_id)
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on GoCardless sync job — possible data leakage attempt blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("GoCardless credential decryption failed for integration %s", integration_id)
        return {"status": "error", "reason": "credential_decryption_failed"}

    access_token = creds.get("access_token", "")
    environment = creds.get("environment", "sandbox")

    if not access_token:
        return {"status": "error", "reason": "missing_access_token"}

    results: dict = {}
    overall_status = "ok"

    # Sync mandates
    mandates_start = time.monotonic()
    try:
        mandates = await gc.get_mandates(access_token, environment)
        mandates_ms = int((time.monotonic() - mandates_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "mandates",
            "status": "success",
            "records_synced": len(mandates),
            "duration_ms": mandates_ms,
        })
        results["mandates"] = len(mandates)
        logger.info(
            "GoCardless mandates synced: tenant=%s count=%d",
            tenant_id,
            len(mandates),
        )
    except Exception as exc:
        overall_status = "partial"
        mandates_ms = int((time.monotonic() - mandates_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "mandates",
            "status": "error",
            "records_synced": 0,
            "duration_ms": mandates_ms,
        })
        results["mandates_error"] = type(exc).__name__
        logger.error("GoCardless mandates sync failed: %s", type(exc).__name__)

    # Sync payments
    payments_start = time.monotonic()
    try:
        payments = await gc.get_payments(access_token, environment)
        payments_ms = int((time.monotonic() - payments_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payments",
            "status": "success",
            "records_synced": len(payments),
            "duration_ms": payments_ms,
        })
        results["payments"] = len(payments)
        logger.info(
            "GoCardless payments synced: tenant=%s count=%d",
            tenant_id,
            len(payments),
        )
    except Exception as exc:
        overall_status = "partial"
        payments_ms = int((time.monotonic() - payments_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payments",
            "status": "error",
            "records_synced": 0,
            "duration_ms": payments_ms,
        })
        results["payments_error"] = type(exc).__name__
        logger.error("GoCardless payments sync failed: %s", type(exc).__name__)

    # Sync payouts
    payouts_start = time.monotonic()
    try:
        payouts = await gc.get_payouts(access_token, environment)
        payouts_ms = int((time.monotonic() - payouts_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payouts",
            "status": "success",
            "records_synced": len(payouts),
            "duration_ms": payouts_ms,
        })
        results["payouts"] = len(payouts)
        logger.info(
            "GoCardless payouts synced: tenant=%s count=%d",
            tenant_id,
            len(payouts),
        )
    except Exception as exc:
        overall_status = "partial"
        payouts_ms = int((time.monotonic() - payouts_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payouts",
            "status": "error",
            "records_synced": 0,
            "duration_ms": payouts_ms,
        })
        results["payouts_error"] = type(exc).__name__
        logger.error("GoCardless payouts sync failed: %s", type(exc).__name__)

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("GoCardless sync aborted — integration %s was disconnected during run", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    # Update integration status to connected after first sync
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected"},
    )

    return {"status": overall_status, **results}


async def enqueue_gocardless_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a GoCardless sync job onto the arq Redis queue."""
    import arq
    from app.core.config import get_settings
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_gocardless_connection", integration_id, tenant_id)
    await redis.aclose()
