"""
Stripe sync job — runs via arq tool.
Fetches recent charges and invoices to verify connection and seed initial data.
"""
import time

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.stripe import client as stripe

logger = get_logger(__name__)


async def sync_stripe_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: verifies Stripe connection is live, fetches recent charges + invoices,
    writes sync logs, and marks integration as connected.
    Returns sync result dict.
    """
    db = get_db()

    logger.info("stripe_sync_started integration_id=%s tenant_id=%s", integration_id, tenant_id)

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("stripe_sync_skipped reason=not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    logger.info("stripe_sync_integration_found id=%s status=%s", integration.id, integration.status)

    if integration.tenant_id != tenant_id:
        logger.error("stripe_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status == "disconnected":
        logger.warning("stripe_sync_skipped reason=disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        access_token = creds.get("access_token", "")
        logger.info("stripe_sync_creds_ok integration_id=%s has_token=%s", integration_id, bool(access_token))
        if not access_token:
            logger.error("stripe_sync_missing_access_token integration_id=%s", integration_id)
            await db.integration.update(where={"id": integration_id}, data={"status": "error"})
            return {"status": "error", "reason": "missing_access_token"}

        # Verify connection is live
        account = await stripe.get_stripe_account(access_token)
        logger.info("stripe_sync_account_verified integration_id=%s stripe_account_id=%s", integration_id, account.get("stripe_account_id"))

        # Fetch charges
        start_ms = int(time.time() * 1000)
        charges = await stripe.fetch_recent_charges(access_token)
        charges_elapsed_ms = int(time.time() * 1000) - start_ms
        logger.info("stripe_sync_charges_fetched integration_id=%s count=%d ms=%d", integration_id, len(charges), charges_elapsed_ms)

        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "charges",
            "status": "success",
            "records_synced": len(charges),
            "duration_ms": charges_elapsed_ms,
        })

        # Fetch invoices
        start_ms = int(time.time() * 1000)
        invoices = await stripe.fetch_recent_invoices(access_token)
        invoices_elapsed_ms = int(time.time() * 1000) - start_ms
        logger.info("stripe_sync_invoices_fetched integration_id=%s count=%d ms=%d", integration_id, len(invoices), invoices_elapsed_ms)

        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "invoices",
            "status": "success",
            "records_synced": len(invoices),
            "duration_ms": invoices_elapsed_ms,
        })

        # Re-read status — integration may have been disconnected while sync was running
        current = await db.integration.find_unique(where={"id": integration_id})
        if not current or current.status == "disconnected":
            logger.info("stripe_sync_aborted reason=disconnected_during_sync integration_id=%s", integration_id)
            return {"status": "skipped", "reason": "disconnected_during_sync"}

        import json
        sync_metadata = {"charges": len(charges), "invoices": len(invoices)}
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "sync_metadata": json.dumps(sync_metadata)},
        )
        logger.info("stripe_sync_ok integration_id=%s charges=%d invoices=%d", integration_id, len(charges), len(invoices))

        return {
            "status": "ok",
            "charges_synced": len(charges),
            "invoices_synced": len(invoices),
            "account": account,
        }

    except Exception as exc:
        logger.error("stripe_sync_failed integration_id=%s exc=%s", integration_id, type(exc).__name__, exc_info=True)
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


async def enqueue_stripe_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_stripe_connection arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_stripe_connection", integration_id, tenant_id)
    await redis.aclose()
