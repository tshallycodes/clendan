"""
SAP S/4HANA Cloud sync job — runs via arq worker.
Fetches supplier invoices and purchase orders, writes sync log entries,
emits events for each invoice received.
"""
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.sap import client as sap
from app.events import enqueue_event
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)


async def sync_sap_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches supplier invoices and purchase orders from SAP S/4HANA Cloud.
    Emits invoice_received events per invoice.
    Writes sync log entries per entity type.
    Updates integration status to connected on success, error on failure.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("sap_sync_skipped integration_id=%s reason=not_found", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("sap_sync_tenant_mismatch integration_id=%s — blocked", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "sap_sync_skipped integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("sap_sync_decrypt_failed integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    client_id = creds.get("client_id", "")
    client_secret = creds.get("client_secret", "")
    token_url = creds.get("token_url", "")
    api_base_url = creds.get("api_base_url", "")

    if not all([client_id, client_secret, token_url, api_base_url]):
        logger.error("sap_sync_missing_credentials integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "missing_credentials"}

    # Always fetch a fresh token — SAP tokens are short-lived
    try:
        token_data = await sap.get_access_token(client_id, client_secret, token_url)
        access_token = token_data["access_token"]
    except Exception as exc:
        logger.error(
            "sap_token_fetch_failed integration_id=%s error=%s",
            integration_id, type(exc).__name__,
        )
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "token_fetch_failed"}

    results: dict = {}

    # --- Supplier Invoices ---
    inv_start = time.monotonic()
    invoices: list = []
    try:
        invoices = await sap.get_supplier_invoices(access_token, api_base_url)
        inv_ms = int((time.monotonic() - inv_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "supplier_invoices",
            "status": "success",
            "records_synced": len(invoices),
            "duration_ms": inv_ms,
        })
        results["supplier_invoices"] = len(invoices)
        logger.info("sap_invoices_synced tenant=%s count=%d", tenant_id, len(invoices))
    except Exception as exc:
        inv_ms = int((time.monotonic() - inv_start) * 1000)
        logger.error(
            "sap_invoices_sync_failed integration_id=%s error=%s",
            integration_id, type(exc).__name__,
        )
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "supplier_invoices",
            "status": "error",
            "records_synced": 0,
            "duration_ms": inv_ms,
        })
        results["supplier_invoices_error"] = type(exc).__name__

    # --- Purchase Orders ---
    po_start = time.monotonic()
    try:
        purchase_orders = await sap.get_purchase_orders(access_token, api_base_url)
        po_ms = int((time.monotonic() - po_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "purchase_orders",
            "status": "success",
            "records_synced": len(purchase_orders),
            "duration_ms": po_ms,
        })
        results["purchase_orders"] = len(purchase_orders)
        logger.info("sap_purchase_orders_synced tenant=%s count=%d", tenant_id, len(purchase_orders))
    except Exception as exc:
        po_ms = int((time.monotonic() - po_start) * 1000)
        logger.error(
            "sap_purchase_orders_sync_failed integration_id=%s error=%s",
            integration_id, type(exc).__name__,
        )
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "purchase_orders",
            "status": "error",
            "records_synced": 0,
            "duration_ms": po_ms,
        })
        results["purchase_orders_error"] = type(exc).__name__

    # --- Emit events for each invoice ---
    for inv in invoices:
        invoice_id = inv.get("SupplierInvoice")
        if not invoice_id:
            continue
        try:
            await enqueue_event(
                tenant_id=tenant_id,
                event_type="invoice_received",
                payload={
                    "source": "sap",
                    "invoice_id": invoice_id,
                    "supplier": inv.get("InvoicingParty"),
                },
                idempotency_key=f"sap:invoice:{invoice_id}",
                db=db,
            )
        except Exception as exc:
            logger.warning(
                "sap_invoice_event_enqueue_failed invoice_id=%s error=%s",
                invoice_id, type(exc).__name__,
            )

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("sap_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected", "last_synced_at": datetime.now(UTC)},
    )

    logger.info("sap_sync_complete tenant=%s results=%s", tenant_id, results)
    return {"status": "ok", **results}


async def enqueue_sap_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_sap_connection arq job onto the Redis queue."""
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_sap_connection", integration_id, tenant_id)
