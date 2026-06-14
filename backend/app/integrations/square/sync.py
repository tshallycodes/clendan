"""
Square sync job — runs via arq tool.
Fetches recent payments and invoices for a connected Square integration.
Writes sync log entries per entity type.
"""
import time

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.square import client as square

logger = get_logger(__name__)


async def sync_square_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches payments and invoices for a Square integration.
    Writes a sync log entry for each entity type.
    Zero trust: validates all data from Square before writing.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("connected", "syncing"):
        logger.warning(
            "Square sync skipped — integration %s not in syncable state",
            integration_id,
        )
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error(
            "Tenant mismatch on Square sync job — possible data leakage attempt blocked"
        )
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error(
            "Square credential decryption failed for integration %s", integration_id
        )
        return {"status": "error", "reason": "credential_decryption_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        return {"status": "error", "reason": "missing_access_token"}

    results: dict = {}
    overall_status = "ok"

    # Verify connection is live before syncing
    try:
        merchant = await square.get_square_merchant(access_token)
        logger.info(
            "Square merchant verified: tenant=%s merchant_id=%s",
            tenant_id,
            merchant.get("merchant_id"),
        )
    except Exception as exc:
        logger.error(
            "Square merchant verification failed for integration %s: %s",
            integration_id,
            type(exc).__name__,
        )
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "error"},
        )
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "connection",
            "status": "error",
            "records_synced": 0,
            "duration_ms": 0,
        })
        return {"status": "error", "reason": type(exc).__name__}

    # Sync payments
    payments_start = time.monotonic()
    try:
        payments = await square.fetch_square_payments(access_token)
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
            "Square payments synced: tenant=%s count=%d",
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
        logger.error("Square payments sync failed: %s", type(exc).__name__)

    # Sync invoices
    invoices_start = time.monotonic()
    try:
        invoices = await square.fetch_square_invoices(access_token)
        invoices_ms = int((time.monotonic() - invoices_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "invoices",
            "status": "success",
            "records_synced": len(invoices),
            "duration_ms": invoices_ms,
        })
        results["invoices"] = len(invoices)
        logger.info(
            "Square invoices synced: tenant=%s count=%d",
            tenant_id,
            len(invoices),
        )
    except Exception as exc:
        overall_status = "partial"
        invoices_ms = int((time.monotonic() - invoices_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "invoices",
            "status": "error",
            "records_synced": 0,
            "duration_ms": invoices_ms,
        })
        results["invoices_error"] = type(exc).__name__
        logger.error("Square invoices sync failed: %s", type(exc).__name__)

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("Square sync aborted — integration %s was disconnected during run", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    # Mark integration as connected after first sync
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected"},
    )

    return {"status": overall_status, **results}


async def enqueue_square_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Square sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_square_connection", integration_id, tenant_id)
    await redis.aclose()
