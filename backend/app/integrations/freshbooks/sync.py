"""
FreshBooks sync job — runs via arq tool.
Fetches invoices, clients, and payments to verify connection and seed initial data.
"""
import time
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.freshbooks import client as fb

logger = get_logger(__name__)


async def sync_freshbooks_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: verify FreshBooks connection is live by fetching invoices, clients, payments.
    Refreshes token if expired. Writes sync log entries. Updates integration status.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("freshbooks_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("freshbooks_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "freshbooks_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("freshbooks_sync_decrypt_failed integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    account_id = creds.get("account_id", "")

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("freshbooks_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await fb.refresh_token(creds["refresh_token"])
                creds = {**creds, **new_tokens}
                access_token = creds["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("freshbooks_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # Resolve account_id if not yet stored
    if not account_id:
        try:
            me = await fb.get_me(access_token)
            account_id = fb.extract_account_id(me)
            creds = {**creds, "account_id": account_id}
            await db.integration.update(
                where={"id": integration_id},
                data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
            )
        except Exception as exc:
            logger.error("freshbooks_get_me_failed integration_id=%s: %s", integration_id, type(exc).__name__)
            await db.integration.update(where={"id": integration_id}, data={"status": "error"})
            await db.integrationsynclog.create(data={
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "entity_type": "profile",
                "status": "error",
                "records_synced": 0,
                "duration_ms": 0,
            })
            return {"status": "error", "reason": "get_me_failed"}

    results: dict = {}

    for entity, fetch_fn in [
        ("invoices", lambda: fb.get_invoices(access_token, account_id)),
        ("clients", lambda: fb.get_clients(access_token, account_id)),
        ("payments", lambda: fb.get_payments(access_token, account_id)),
    ]:
        start = time.monotonic()
        entity_status = "success"
        count = 0
        try:
            records = await fetch_fn()
            count = len(records)
        except Exception as exc:
            logger.error(
                "freshbooks_sync_%s_failed integration_id=%s: %s",
                entity, integration_id, type(exc).__name__,
            )
            entity_status = "error"

        elapsed_ms = int((time.monotonic() - start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": entity,
            "status": entity_status,
            "records_synced": count,
            "duration_ms": elapsed_ms,
        })
        results[entity] = {"status": entity_status, "count": count}

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("freshbooks_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    any_success = any(v["status"] == "success" for v in results.values())
    if any_success:
        await db.integration.update(
            where={"id": integration_id},
            data={
                "status": "connected",
                "connected_at": datetime.now(UTC),
                "last_synced_at": datetime.now(UTC),
            },
        )
        logger.info(
            "freshbooks_sync_ok tenant=%s invoices=%d clients=%d payments=%d",
            tenant_id,
            results["invoices"]["count"],
            results["clients"]["count"],
            results["payments"]["count"],
        )
        return {"status": "ok", **{k: v["count"] for k, v in results.items()}}
    else:
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        logger.error("freshbooks_sync_all_entities_failed integration_id=%s", integration_id)
        return {"status": "error", "reason": "all_entity_fetches_failed"}


async def enqueue_freshbooks_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_freshbooks_connection arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_freshbooks_connection", integration_id, tenant_id)
    await redis.aclose()
