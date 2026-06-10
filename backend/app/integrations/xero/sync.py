"""
Xero sync job — runs via arq worker.
Fetches accounts and contacts to verify connection is live.
Writes IntegrationSyncLog entries. Updates integration status.
"""
import time
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.xero import client as xero

logger = get_logger(__name__)


async def sync_xero_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: verify Xero connection is live by fetching accounts and contacts.
    Writes sync log entries. Updates integration status to connected or error.
    Returns sync result dict.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("xero_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("xero_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "xero_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("xero_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    xero_tenant_id = creds.get("xero_tenant_id", "")
    if not xero_tenant_id:
        logger.error("xero_sync_no_tenant_id integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "no_xero_tenant_id"}

    access_token = creds.get("access_token", "")
    refresh_token_val = creds.get("refresh_token", "")

    # Attempt token refresh if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            from datetime import datetime, UTC
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("xero_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await xero.refresh_xero_token(refresh_token_val)
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("xero_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # Fetch accounts
    accounts_start = time.monotonic()
    accounts_status = "success"
    accounts_count = 0
    try:
        accounts = await xero.get_accounts(access_token, xero_tenant_id)
        accounts_count = len(accounts)
    except Exception as exc:
        logger.error("xero_sync_accounts_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        accounts_status = "error"

    accounts_elapsed = int((time.monotonic() - accounts_start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration.id,
        "entity_type": "accounts",
        "status": accounts_status,
        "records_synced": accounts_count,
        "duration_ms": accounts_elapsed,
    })

    # Fetch contacts
    contacts_start = time.monotonic()
    contacts_status = "success"
    contacts_count = 0
    try:
        contacts = await xero.get_contacts(access_token, xero_tenant_id)
        contacts_count = len(contacts)
    except Exception as exc:
        logger.error("xero_sync_contacts_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        contacts_status = "error"

    contacts_elapsed = int((time.monotonic() - contacts_start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration.id,
        "entity_type": "contacts",
        "status": contacts_status,
        "records_synced": contacts_count,
        "duration_ms": contacts_elapsed,
    })

    # Determine overall outcome
    if accounts_status == "success" or contacts_status == "success":
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "connected_at": datetime.now(UTC)},
        )
        logger.info(
            "xero_sync_ok tenant=%s accounts=%d contacts=%d",
            tenant_id, accounts_count, contacts_count,
        )
        return {
            "status": "ok",
            "accounts_synced": accounts_count,
            "contacts_synced": contacts_count,
        }
    else:
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        logger.error("xero_sync_failed_all_entities integration_id=%s", integration_id)
        return {"status": "error", "reason": "all_entity_fetches_failed"}


async def enqueue_xero_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Xero sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_xero_connection", integration_id, tenant_id)
    await redis.aclose()
