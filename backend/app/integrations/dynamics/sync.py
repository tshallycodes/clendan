"""
Dynamics 365 sync job — runs via arq worker.
Fetches invoices, accounts, and opportunities from the Dynamics Web API,
writes sync logs, and emits orchestrator events for downstream processing.
"""
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.dynamics import client as dynamics
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)


async def sync_dynamics_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: refreshes token if needed, fetches invoices/accounts/opportunities,
    emits invoice_received orchestrator events, marks integration connected.
    Returns sync result dict.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("dynamics_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("dynamics_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "dynamics_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("dynamics_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    org_url = creds.get("dynamics_org_url", "")

    if not access_token or not org_url:
        logger.error("dynamics_sync_missing_credentials integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "missing_credentials"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("dynamics_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await dynamics.refresh_dynamics_token(creds.get("refresh_token", ""))
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("dynamics_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # ---------------------------------------------------------------------------
    # Fetch entities
    # ---------------------------------------------------------------------------
    invoices: list = []
    accounts: list = []
    opportunities: list = []

    for entity_type, fetch_fn, result_list in [
        ("invoices", lambda: dynamics.get_invoices(access_token, org_url), invoices),
        ("accounts", lambda: dynamics.get_accounts(access_token, org_url), accounts),
        ("opportunities", lambda: dynamics.get_opportunities(access_token, org_url), opportunities),
    ]:
        start = time.monotonic()
        sync_status = "success"
        records: list = []
        try:
            records = await fetch_fn()
            result_list.extend(records)
            logger.info("dynamics_sync_%s integration_id=%s count=%d", entity_type, integration_id, len(records))
        except Exception as exc:
            logger.error("dynamics_sync_%s_failed integration_id=%s: %s", entity_type, integration_id, type(exc).__name__)
            sync_status = "error"

        elapsed_ms = int((time.monotonic() - start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": entity_type,
            "status": sync_status,
            "records_synced": len(records),
            "duration_ms": elapsed_ms,
        })

    # ---------------------------------------------------------------------------
    # Emit orchestrator events for invoices
    # ---------------------------------------------------------------------------
    try:
        from app.orchestrator.events import enqueue_orchestrator_event
        for inv in invoices:
            invoice_id = inv.get("invoiceid")
            if invoice_id:
                await enqueue_orchestrator_event(
                    tenant_id=tenant_id,
                    event_type="invoice_received",
                    payload={
                        "source": "dynamics",
                        "entity_type": "invoice",
                        "entity_id": invoice_id,
                        "org_url": org_url,
                    },
                    idempotency_key=f"dynamics:invoice:{invoice_id}",
                    db=db,
                )
    except Exception as exc:
        logger.error("dynamics_invoice_event_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # ---------------------------------------------------------------------------
    # Update integration status
    # ---------------------------------------------------------------------------
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("dynamics_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected", "last_synced_at": datetime.now(UTC)},
    )

    logger.info(
        "dynamics_sync_ok tenant=%s invoices=%d accounts=%d opportunities=%d",
        tenant_id, len(invoices), len(accounts), len(opportunities),
    )
    return {
        "status": "ok",
        "invoices": len(invoices),
        "accounts": len(accounts),
        "opportunities": len(opportunities),
    }


async def enqueue_dynamics_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues sync_dynamics_connection as an arq job onto the Redis queue."""
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_dynamics_connection", integration_id, tenant_id)
