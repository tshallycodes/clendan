"""
FreshBooks sync job — runs via arq worker.
Fetches invoices, clients, payments, and expenses then persists them to the DB.
"""
import time
from datetime import datetime, UTC

from prisma import Json
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.freshbooks import client as fb

logger = get_logger(__name__)

_INVOICE_STATUS_MAP = {
    # v3_status values
    "draft": "draft",
    "sent": "sent",
    "viewed": "sent",
    "paid": "paid",
    "auto-paid": "paid",
    "retry": "partial",
    "failed": "partial",
    "partial": "partial",
    "disputed": "void",
    "void": "void",
    # payment_status values
    "unpaid": "sent",
    "overdue": "overdue",
}


def _parse_date(raw: str | None) -> datetime | None:
    """Parse a YYYY-MM-DD string to a UTC datetime. Returns None on failure."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _cents(value: object) -> int:
    """Convert a raw FreshBooks amount value (float string or number) to integer cents."""
    try:
        return int(float(value or 0) * 100)
    except (TypeError, ValueError):
        return 0


async def sync_freshbooks_connection(_ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetch FreshBooks invoices, clients, payments, expenses and persist to DB.
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
    fetched: dict = {}

    for entity, fetch_fn in [
        ("invoices", lambda: fb.get_invoices(access_token, account_id)),
        ("clients", lambda: fb.get_clients(access_token, account_id)),
        ("payments", lambda: fb.get_payments(access_token, account_id)),
        ("expenses", lambda: fb.get_expenses(access_token, account_id)),
    ]:
        start = time.monotonic()
        entity_status = "success"
        records: list = []
        try:
            records = await fetch_fn()
            await _upsert_entities(db, entity, records, integration_id, tenant_id)
        except Exception as exc:
            logger.error(
                "freshbooks_sync_%s_failed integration_id=%s: %s — %s",
                entity, integration_id, type(exc).__name__, exc,
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
        results[entity] = {"status": entity_status, "count": len(records)}
        fetched[entity] = records

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("freshbooks_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    any_success = any(v["status"] == "success" for v in results.values())
    if any_success:
        sync_metadata = _build_freshbooks_metadata(fetched)
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
            "freshbooks_sync_ok tenant=%s invoices=%d clients=%d payments=%d expenses=%d",
            tenant_id,
            results["invoices"]["count"],
            results["clients"]["count"],
            results["payments"]["count"],
            results["expenses"]["count"],
        )
        return {"status": "ok", **{k: v["count"] for k, v in results.items()}}
    else:
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        logger.error("freshbooks_sync_all_entities_failed integration_id=%s", integration_id)
        return {"status": "error", "reason": "all_entity_fetches_failed"}


async def _upsert_entities(db, entity: str, records: list, integration_id: str, tenant_id: str) -> None:
    """Dispatch upserts for a given entity type."""
    if entity == "invoices":
        for inv in records:
            await _upsert_invoice(db, inv, integration_id, tenant_id)
    elif entity == "clients":
        for client in records:
            await _upsert_contact(db, client, integration_id, tenant_id)
    elif entity == "payments":
        for pmt in records:
            await _upsert_payment(db, pmt, integration_id, tenant_id)
    elif entity == "expenses":
        for exp in records:
            await _upsert_expense(db, exp, integration_id, tenant_id)


async def _upsert_invoice(db, inv: dict, integration_id: str, tenant_id: str) -> None:
    ext_id = str(inv["id"])
    raw_status = inv.get("payment_status") or inv.get("v3_status", "")
    status = _INVOICE_STATUS_MAP.get(raw_status, "draft")

    total_cents = _cents((inv.get("amount") or {}).get("amount"))
    tax_cents = _cents((inv.get("tax_amount") or {}).get("amount"))
    subtotal_cents = total_cents - tax_cents
    outstanding_cents = _cents((inv.get("outstanding") or {}).get("amount"))
    due_date = _parse_date(inv.get("due_date") or inv.get("duedate"))
    issue_date = _parse_date(inv.get("create_date"))

    shared = {
        "number": inv.get("invoice_number") or inv.get("number"),
        "status": status,
        "contact_name": inv.get("customer_name") or inv.get("organization"),
        "currency": inv.get("currency_code", "GBP"),
        "total_cents": total_cents,
        "outstanding_cents": outstanding_cents,
        "tax_cents": tax_cents,
        "subtotal_cents": subtotal_cents,
        "due_date": due_date,
        "issue_date": issue_date,
        "type": "invoice",
        "raw_data": inv,
    }
    await db.accountinginvoice.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": ext_id}},
        data={
            "create": {**shared, "tenant_id": tenant_id, "integration_id": integration_id, "source": "freshbooks", "external_id": ext_id},
            "update": shared,
        },
    )


async def _upsert_contact(db, client: dict, integration_id: str, tenant_id: str) -> None:
    ext_id = str(client["id"])
    name = (
        client.get("organization")
        or f'{client.get("fname", "")} {client.get("lname", "")}'.strip()
        or None
    )
    shared = {
        "name": name,
        "email": client.get("email"),
        "contact_type": "customer",
    }
    await db.accountingcontact.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": ext_id}},
        data={
            "create": {**shared, "tenant_id": tenant_id, "integration_id": integration_id, "source": "freshbooks", "external_id": ext_id},
            "update": shared,
        },
    )


async def _upsert_payment(db, pmt: dict, integration_id: str, tenant_id: str) -> None:
    ext_id = str(pmt["id"])
    shared = {
        "amount_cents": _cents((pmt.get("amount") or {}).get("amount")),
        "currency": pmt.get("currency_code", "GBP"),
        "paid_at": _parse_date(pmt.get("date")),
        "payment_type": "received",
    }
    await db.accountingpayment.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": ext_id}},
        data={
            "create": {**shared, "tenant_id": tenant_id, "integration_id": integration_id, "source": "freshbooks", "external_id": ext_id},
            "update": shared,
        },
    )


async def _upsert_expense(db, exp: dict, integration_id: str, tenant_id: str) -> None:
    ext_id = str(exp["id"])
    category_raw = exp.get("category")
    category = category_raw.get("name") if isinstance(category_raw, dict) else None
    shared = {
        "amount_cents": _cents((exp.get("amount") or {}).get("amount")),
        "tax_cents": _cents((exp.get("tax_amount") or {}).get("amount")),
        "category": category,
        "description": exp.get("notes"),
        "contact_name": exp.get("vendor"),
        "expense_date": _parse_date(exp.get("date")),
        "approved": exp.get("status") == 1,
    }
    await db.accountingexpense.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": ext_id}},
        data={
            "create": {**shared, "tenant_id": tenant_id, "integration_id": integration_id, "source": "freshbooks", "external_id": ext_id},
            "update": shared,
        },
    )


def _build_freshbooks_metadata(fetched: dict) -> dict:
    """Compute summary stats from raw FreshBooks API data for display in the UI."""
    invoices = fetched.get("invoices", [])
    clients = fetched.get("clients", [])
    payments = fetched.get("payments", [])
    expenses = fetched.get("expenses", [])

    unpaid_statuses = {"sent", "viewed", "partial", "retry", "failed"}
    overdue_statuses = {"sent", "viewed", "partial"}

    outstanding_cents = 0
    overdue_cents = 0
    overdue_count = 0

    now_date = datetime.now(UTC).date()

    for inv in invoices:
        status = inv.get("payment_status") or inv.get("v3_status", "")
        amount_cents = _cents((inv.get("outstanding") or {}).get("amount"))

        if status in unpaid_statuses:
            outstanding_cents += amount_cents

        due_date_str = inv.get("due_date") or inv.get("duedate")
        if status in overdue_statuses and due_date_str:
            try:
                due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                if due < now_date:
                    overdue_count += 1
                    overdue_cents += amount_cents
            except ValueError:
                pass

    total_payments_cents = sum(
        _cents((pmt.get("amount") or {}).get("amount")) for pmt in payments
    )
    total_expenses_cents = sum(
        _cents((exp.get("amount") or {}).get("amount")) for exp in expenses
    )

    return {
        "total_invoices": len(invoices),
        "outstanding_invoices": sum(
            1 for inv in invoices
            if (inv.get("payment_status") or inv.get("v3_status", "")) in unpaid_statuses
        ),
        "outstanding_amount_cents": outstanding_cents,
        "overdue_invoices": overdue_count,
        "overdue_amount_cents": overdue_cents,
        "total_clients": len(clients),
        "total_payments": len(payments),
        "total_payments_amount_cents": total_payments_cents,
        "total_expenses": len(expenses),
        "total_expenses_amount_cents": total_expenses_cents,
    }


async def enqueue_freshbooks_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_freshbooks_connection arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_freshbooks_connection", integration_id, tenant_id)
    await redis.aclose()
