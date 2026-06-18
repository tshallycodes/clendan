"""
QuickBooks sync job — runs via arq worker.
Fetches all financial entities and persists them to the database.
"""
import time
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.encryption import decrypt as decrypt_field
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.quickbooks import client as qb
from app.integrations.quickbooks.persist import (
    upsert_invoice,
    upsert_bill,
    upsert_customer,
    upsert_vendor,
    upsert_payment,
    upsert_expense,
    upsert_account,
    upsert_tax_rate,
    upsert_credit_note,
)

logger = get_logger(__name__)


async def _compute_financial_summary(db, integration_id: str, results: dict) -> dict:
    """
    Queries the DB after sync to compute financial aggregates for the drawer.
    Falls back to entity counts if any query fails.
    """
    try:
        now = datetime.now(UTC)

        inv_all = await db.accountinginvoice.find_many(where={"integration_id": integration_id})
        # QB persist uses "sent" and "overdue" for outstanding invoices
        inv_outstanding = [i for i in inv_all if i.status in ("sent", "overdue")]

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
        logger.warning("qb_financial_summary_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        return {entity: v["count"] for entity, v in results.items()}


async def sync_quickbooks_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetch all QB entities and persist to DB.
    Refreshes token if expired. Writes per-entity sync logs. Updates integration status.
    """
    logger.info("qb_sync_started integration_id=%s tenant_id=%s", integration_id, tenant_id)
    try:
        return await _sync_quickbooks_connection(integration_id, tenant_id)
    except Exception as exc:
        logger.error("qb_sync_unhandled_error integration_id=%s: %s — %s", integration_id, type(exc).__name__, exc)
        try:
            db = get_db()
            await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        except Exception:
            pass
        return {"status": "error", "reason": "unhandled_exception"}


async def _sync_quickbooks_connection(integration_id: str, tenant_id: str) -> dict:
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("qb_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("qb_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "qb_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("qb_sync_decrypt_failed integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("qb_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await qb.refresh_token(creds["refresh_token"])
                creds = {**creds, **new_tokens}
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error(
                "qb_token_refresh_failed integration_id=%s: %s",
                integration_id, type(exc).__name__,
            )

    access_token = decrypt_field(creds.get("access_token", ""))
    realm_id = creds.get("realm_id", "")
    sandbox = settings.quickbooks_sandbox

    # Entity definitions: (name, fetch_fn, upsert_fn)
    entity_plan = [
        ("invoices",     lambda: qb.get_invoices(access_token, realm_id, sandbox),     upsert_invoice),
        ("bills",        lambda: qb.get_bills(access_token, realm_id, sandbox),        upsert_bill),
        ("customers",    lambda: qb.get_customers(access_token, realm_id, sandbox),    upsert_customer),
        ("vendors",      lambda: qb.get_vendors(access_token, realm_id, sandbox),      upsert_vendor),
        ("payments",     lambda: qb.get_payments(access_token, realm_id, sandbox),     upsert_payment),
        ("expenses",     lambda: qb.get_expenses(access_token, realm_id, sandbox),     upsert_expense),
        ("accounts",     lambda: qb.get_accounts(access_token, realm_id, sandbox),     upsert_account),
        ("tax_codes",    lambda: qb.get_tax_codes(access_token, realm_id, sandbox),    upsert_tax_rate),
        ("credit_memos", lambda: qb.get_credit_memos(access_token, realm_id, sandbox), upsert_credit_note),
    ]

    results: dict[str, dict] = {}

    for entity, fetch_fn, persist_fn in entity_plan:
        start = time.monotonic()
        entity_status = "success"
        records: list = []
        error_message: str | None = None

        try:
            records = await fetch_fn()
            for item in records:
                try:
                    await persist_fn(integration_id, tenant_id, item)
                except Exception as exc:
                    logger.error(
                        "qb_upsert_failed entity=%s id=%s integration_id=%s: %s",
                        entity, item.get("Id", "?"), integration_id, type(exc).__name__,
                    )
        except Exception as exc:
            logger.error(
                "qb_fetch_failed entity=%s integration_id=%s: %s",
                entity, integration_id, type(exc).__name__,
            )
            entity_status = "error"
            error_message = type(exc).__name__

        elapsed_ms = int((time.monotonic() - start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": entity,
            "status": entity_status,
            "records_synced": len(records),
            "error_message": error_message,
            "duration_ms": elapsed_ms,
        })
        results[entity] = {"status": entity_status, "count": len(records)}

    # Guard: abort update if integration was disconnected during sync
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("qb_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    any_success = any(v["status"] == "success" for v in results.values())
    if any_success:
        sync_metadata = await _compute_financial_summary(db, integration_id, results)
        await db.integration.update(
            where={"id": integration_id},
            data={
                "status": "connected",
                "last_synced_at": datetime.now(UTC),
                "sync_metadata": sync_metadata,
            },
        )
        logger.info(
            "qb_sync_ok tenant=%s %s",
            tenant_id,
            " ".join(f"{k}={v['count']}" for k, v in results.items()),
        )
        return {"status": "ok", **sync_metadata}
    else:
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        logger.error("qb_sync_all_entities_failed integration_id=%s", integration_id)
        return {"status": "error", "reason": "all_entity_fetches_failed"}


async def enqueue_quickbooks_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_quickbooks_connection arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_quickbooks_connection", integration_id, tenant_id)
    await redis.aclose()
