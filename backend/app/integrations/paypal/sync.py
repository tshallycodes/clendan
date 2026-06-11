"""
PayPal sync job — runs via arq worker.
Fetches recent transactions and invoices for a connected PayPal integration.
Writes sync log entries per entity type.
"""
import time

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.paypal import client as paypal

logger = get_logger(__name__)


async def sync_paypal_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches transactions and invoices for a PayPal integration.
    Writes a sync log entry for each entity type.
    Zero trust: validates all data from PayPal before writing.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("connected", "syncing"):
        logger.warning(
            "PayPal sync skipped — integration %s not in syncable state",
            integration_id,
        )
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error(
            "Tenant mismatch on PayPal sync job — possible data leakage attempt blocked"
        )
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error(
            "PayPal credential decryption failed for integration %s", integration_id
        )
        return {"status": "error", "reason": "credential_decryption_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        return {"status": "error", "reason": "missing_access_token"}

    results: dict = {}
    overall_status = "ok"

    # Verify connection is live before syncing
    try:
        merchant = await paypal.get_paypal_merchant_info(access_token)
        logger.info(
            "PayPal merchant verified: tenant=%s user_id=%s",
            tenant_id,
            merchant.get("user_id"),
        )
    except Exception as exc:
        logger.error(
            "PayPal merchant verification failed for integration %s: %s",
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

    # Sync transactions
    transactions_start = time.monotonic()
    try:
        transactions = await paypal.fetch_paypal_transactions(access_token)
        transactions_ms = int((time.monotonic() - transactions_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transactions",
            "status": "success",
            "records_synced": len(transactions),
            "duration_ms": transactions_ms,
        })
        results["transactions"] = len(transactions)
        logger.info(
            "PayPal transactions synced: tenant=%s count=%d",
            tenant_id,
            len(transactions),
        )
    except Exception as exc:
        overall_status = "partial"
        transactions_ms = int((time.monotonic() - transactions_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transactions",
            "status": "error",
            "records_synced": 0,
            "duration_ms": transactions_ms,
        })
        results["transactions_error"] = type(exc).__name__
        logger.error("PayPal transactions sync failed: %s", type(exc).__name__)

    # Sync invoices
    invoices_start = time.monotonic()
    try:
        invoices = await paypal.fetch_paypal_invoices(access_token)
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
            "PayPal invoices synced: tenant=%s count=%d",
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
        logger.error("PayPal invoices sync failed: %s", type(exc).__name__)

    # Mark integration as connected after first sync
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected"},
    )

    return {"status": overall_status, **results}


async def enqueue_paypal_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a PayPal sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_paypal_connection", integration_id, tenant_id)
    await redis.aclose()
