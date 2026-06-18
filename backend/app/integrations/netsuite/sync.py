"""
NetSuite sync job — runs via arq worker.
Fetches invoices, vendors, and purchase orders; emits orchestrator events; updates integration status.
"""
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.netsuite import client as netsuite
from app.orchestrator.events import enqueue_orchestrator_event

logger = get_logger(__name__)


async def sync_netsuite_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetch NetSuite invoices, vendors, purchase orders; emit invoice_received
    events; write sync logs; mark integration as connected.
    Returns sync result dict.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("netsuite_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("netsuite_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "netsuite_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("netsuite_sync_decrypt_failed integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    account_id = creds.get("account_id", "")
    if not account_id:
        logger.error("netsuite_sync_missing_account_id integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "missing_account_id"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("netsuite_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await netsuite.refresh_netsuite_token(
                    creds.get("refresh_token", ""), account_id
                )
                creds = {**creds, **new_tokens}
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error(
                "netsuite_token_refresh_failed integration_id=%s: %s",
                integration_id, type(exc).__name__,
            )

    access_token = creds.get("access_token", "")

    results: dict = {}

    for entity, fetch_fn in [
        ("invoices", lambda: netsuite.get_invoices(access_token, account_id)),
        ("vendors", lambda: netsuite.get_vendors(access_token, account_id)),
        ("purchase_orders", lambda: netsuite.get_purchase_orders(access_token, account_id)),
    ]:
        start = time.monotonic()
        entity_status = "success"
        records: list = []
        try:
            records = await fetch_fn()
        except Exception as exc:
            logger.error(
                "netsuite_sync_%s_failed integration_id=%s: %s",
                entity, integration_id, type(exc).__name__,
            )
            entity_status = "error"

        elapsed_ms = int((time.monotonic() - start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": entity,
            "status": entity_status,
            "records_synced": len(records),
            "duration_ms": elapsed_ms,
        })
        results[entity] = {"status": entity_status, "records": records}

    # Emit invoice_received events for each invoice
    invoices = results.get("invoices", {}).get("records", [])
    for inv in invoices:
        inv_id = inv.get("id")
        if not inv_id:
            continue
        try:
            await enqueue_orchestrator_event(
                tenant_id=tenant_id,
                event_type="invoice_received",
                payload={
                    "source": "netsuite",
                    "account_id": account_id,
                    "invoice_id": inv_id,
                    "invoice_number": inv.get("tranId"),
                },
                idempotency_key=f"netsuite:invoice:{inv_id}",
                db=db,
            )
        except Exception as exc:
            logger.error(
                "netsuite_invoice_event_failed integration_id=%s invoice_id=%s: %s",
                integration_id, inv_id, type(exc).__name__,
            )

    # Re-check in case disconnected during sync
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("netsuite_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    await db.integration.update(
        where={"id": integration_id},
        data={
            "status": "connected",
            "connected_at": datetime.now(UTC),
            "last_synced_at": datetime.now(UTC),
        },
    )

    logger.info(
        "netsuite_sync_ok tenant=%s invoices=%d vendors=%d purchase_orders=%d",
        tenant_id,
        len(results.get("invoices", {}).get("records", [])),
        len(results.get("vendors", {}).get("records", [])),
        len(results.get("purchase_orders", {}).get("records", [])),
    )
    return {
        "status": "ok",
        "invoices": len(results.get("invoices", {}).get("records", [])),
        "vendors": len(results.get("vendors", {}).get("records", [])),
        "purchase_orders": len(results.get("purchase_orders", {}).get("records", [])),
    }


async def enqueue_netsuite_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_netsuite_connection arq job onto the Redis queue."""
    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_netsuite_connection", integration_id, tenant_id)
