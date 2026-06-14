"""
Adyen sync job — runs via arq worker.
Validates connection and fetches payment methods for a connected Adyen integration.
Writes sync log entries per entity type.
"""
import time

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.adyen import client as adyen

logger = get_logger(__name__)


async def sync_adyen_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: validates Adyen connection and fetches payment methods.
    Writes a sync log entry for each entity type.
    Zero trust: validates all data from Adyen before writing.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("connected", "syncing"):
        logger.warning(
            "Adyen sync skipped — integration %s not in syncable state",
            integration_id,
        )
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error(
            "Tenant mismatch on Adyen sync job — possible data leakage attempt blocked"
        )
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error(
            "Adyen credential decryption failed for integration %s", integration_id
        )
        return {"status": "error", "reason": "credential_decryption_failed"}

    api_key = creds.get("api_key", "")
    merchant_account = creds.get("merchant_account", "")
    environment = creds.get("environment", "test")

    if not api_key or not merchant_account:
        return {"status": "error", "reason": "missing_credentials"}

    # Verify connection is live before syncing
    try:
        merchant = await adyen.validate_connection(api_key, merchant_account, environment)
        logger.info(
            "Adyen merchant verified: tenant=%s merchant_id=%s",
            tenant_id,
            merchant.get("merchant_id"),
        )
    except Exception as exc:
        logger.error(
            "Adyen merchant verification failed for integration %s: %s",
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

    results: dict = {}
    overall_status = "ok"

    # Sync payment methods
    pm_start = time.monotonic()
    try:
        payment_methods = await adyen.fetch_payments(api_key, merchant_account, environment)
        pm_ms = int((time.monotonic() - pm_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payment_methods",
            "status": "success",
            "records_synced": len(payment_methods),
            "duration_ms": pm_ms,
        })
        results["payment_methods"] = len(payment_methods)
        logger.info(
            "Adyen payment methods synced: tenant=%s count=%d",
            tenant_id,
            len(payment_methods),
        )
    except Exception as exc:
        overall_status = "partial"
        pm_ms = int((time.monotonic() - pm_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "payment_methods",
            "status": "error",
            "records_synced": 0,
            "duration_ms": pm_ms,
        })
        results["payment_methods_error"] = type(exc).__name__
        logger.error("Adyen payment methods sync failed: %s", type(exc).__name__)

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info(
            "Adyen sync aborted — integration %s was disconnected during run",
            integration_id,
        )
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    # Mark integration as connected after first successful sync
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected"},
    )

    return {"status": overall_status, **results}


async def enqueue_adyen_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues an Adyen sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_adyen_connection", integration_id, tenant_id)
    await redis.aclose()
