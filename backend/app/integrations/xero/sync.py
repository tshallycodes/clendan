"""
Xero sync job — runs via arq worker.
Fetches all financial entities from Xero and persists them to the database.
Writes IntegrationSyncLog entries per entity. Updates integration status.
"""
import time
from datetime import datetime, UTC

from prisma import Json
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.xero import client as xero
from app.integrations.xero.persist import (
    upsert_accounts,
    upsert_bills,
    upsert_contacts,
    upsert_credit_notes,
    upsert_expenses,
    upsert_invoices,
    upsert_payments,
    upsert_tax_rates,
)

logger = get_logger(__name__)


async def _sync_entity(
    db,
    *,
    entity: str,
    fetch_fn,
    upsert_fn,
    integration_id: str,
    tenant_id: str,
) -> dict:
    """
    Fetches one entity type from Xero and upserts it into the DB.
    Returns {"status": "success"|"error", "count": int}.
    Always writes an IntegrationSyncLog row.
    """
    start = time.monotonic()
    status = "success"
    count = 0
    try:
        records = await fetch_fn()
        count = await upsert_fn(db, integration_id, tenant_id, records)
    except Exception as exc:
        logger.error(
            "xero_sync_%s_failed integration_id=%s: %s",
            entity, integration_id, type(exc).__name__,
        )
        status = "error"

    elapsed_ms = int((time.monotonic() - start) * 1000)
    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "entity_type": entity,
        "status": status,
        "records_synced": count,
        "duration_ms": elapsed_ms,
    })
    return {"status": status, "count": count}


async def _compute_financial_summary(db, integration_id: str, results: dict) -> dict:
    """
    Queries the DB after sync to compute financial aggregates for the drawer.
    Falls back to entity counts if any query fails.
    """
    try:
        now = datetime.now(UTC)

        inv_all = await db.accountinginvoice.find_many(where={"integration_id": integration_id})
        inv_outstanding = [i for i in inv_all if i.status == "sent"]

        def _is_overdue(inv) -> bool:
            if not inv.due_date:
                return False
            due = inv.due_date
            if due.tzinfo is None:
                from datetime import timezone
                due = due.replace(tzinfo=timezone.utc)
            return due < now

        inv_overdue = [i for i in inv_outstanding if _is_overdue(i)]

        contacts_count = await db.accountingcontact.count(where={"integration_id": integration_id})

        payments = await db.accountingpayment.find_many(where={"integration_id": integration_id})
        expenses = await db.accountingexpense.find_many(where={"integration_id": integration_id})

        return {
            "total_invoices": len(inv_all),
            "outstanding_invoices": len(inv_outstanding),
            "outstanding_amount_cents": sum(i.outstanding_cents for i in inv_outstanding),
            "overdue_invoices": len(inv_overdue),
            "overdue_amount_cents": sum(i.outstanding_cents for i in inv_overdue),
            "total_clients": contacts_count,
            "total_payments": len(payments),
            "total_payments_amount_cents": sum(p.amount_cents for p in payments),
            "total_expenses": len(expenses),
            "total_expenses_amount_cents": sum(e.amount_cents for e in expenses),
        }
    except Exception as exc:
        logger.warning("xero_financial_summary_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        return {entity: v["count"] for entity, v in results.items()}


async def sync_xero_connection(_ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: sync all Xero financial entities to the database.
    Refreshes token if expired. Persists invoices, bills, contacts, payments,
    expenses, accounts, credit notes, and tax rates.
    Writes sync log entries. Updates integration status and sync_metadata.
    """
    logger.info("xero_sync_started integration_id=%s tenant_id=%s", integration_id, tenant_id)
    try:
        return await _sync_xero_connection(integration_id, tenant_id)
    except Exception as exc:
        logger.error("xero_sync_unhandled_error integration_id=%s: %s — %s", integration_id, type(exc).__name__, exc)
        try:
            db = get_db()
            await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        except Exception:
            pass
        return {"status": "error", "reason": "unhandled_exception"}


async def _sync_xero_connection(integration_id: str, tenant_id: str) -> dict:
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

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("xero_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await xero.refresh_xero_token(creds.get("refresh_token", ""))
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("xero_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # Sync all entity types
    entity_configs = [
        ("invoices",    lambda: xero.get_invoices(access_token, xero_tenant_id),     upsert_invoices),
        ("bills",       lambda: xero.get_bills(access_token, xero_tenant_id),        upsert_bills),
        ("contacts",    lambda: xero.get_contacts(access_token, xero_tenant_id),     upsert_contacts),
        ("payments",    lambda: xero.get_payments(access_token, xero_tenant_id),     upsert_payments),
        ("expenses",    lambda: xero.get_expenses(access_token, xero_tenant_id),     upsert_expenses),
        ("accounts",    lambda: xero.get_accounts(access_token, xero_tenant_id),     upsert_accounts),
        ("credit_notes", lambda: xero.get_credit_notes(access_token, xero_tenant_id), upsert_credit_notes),
        ("tax_rates",   lambda: xero.get_tax_rates(access_token, xero_tenant_id),    upsert_tax_rates),
    ]

    results: dict[str, dict] = {}
    for entity, fetch_fn, upsert_fn in entity_configs:
        results[entity] = await _sync_entity(
            db,
            entity=entity,
            fetch_fn=fetch_fn,
            upsert_fn=upsert_fn,
            integration_id=integration_id,
            tenant_id=tenant_id,
        )

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("xero_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    any_success = any(v["status"] == "success" for v in results.values())
    if any_success:
        sync_metadata = await _compute_financial_summary(db, integration_id, results)
        await db.integration.update(
            where={"id": integration_id},
            data={
                "status": "connected",
                "connected_at": datetime.now(UTC),
                "last_synced_at": datetime.now(UTC),
                "sync_metadata": Json(sync_metadata),
            },
        )
        logger.info(
            "xero_sync_ok tenant=%s %s",
            tenant_id,
            " ".join(f"{e}={v['count']}" for e, v in results.items()),
        )
        return {"status": "ok", **{e: v["count"] for e, v in results.items()}}

    await db.integration.update(where={"id": integration_id}, data={"status": "error"})
    logger.error("xero_sync_failed_all_entities integration_id=%s", integration_id)
    return {"status": "error", "reason": "all_entity_fetches_failed"}


async def enqueue_xero_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Xero sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_xero_connection", integration_id, tenant_id)
    await redis.aclose()
