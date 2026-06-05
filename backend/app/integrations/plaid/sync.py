"""
Plaid sync job — runs via arq worker.
Fetches and stores bank accounts + transactions for a connected Plaid item.
"""
import json
from datetime import datetime

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.plaid import client as plaid

logger = get_logger(__name__)


async def sync_plaid_transactions(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: syncs all transactions for a Plaid integration.
    Uses cursor-based pagination. Stores accounts + transactions in DB.
    Zero trust: validates all data from Plaid before writing.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on Plaid sync — blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    creds = json.loads(integration.encrypted_credentials)
    encrypted_access = creds.get("access_token", "")
    item_id = creds.get("item_id", "")

    if not encrypted_access or not item_id:
        return {"status": "error", "reason": "incomplete_credentials"}

    try:
        # Sync accounts first
        accounts_data = await plaid.get_accounts(encrypted_access)
        accounts_synced = 0
        for acct in accounts_data:
            plaid_account_id = acct.get("account_id", "")
            if not plaid_account_id:
                continue
            balance = acct.get("balances", {})
            current = balance.get("current") or 0.0
            currency = balance.get("iso_currency_code") or "USD"

            existing = await db.bankaccount.find_unique(where={"plaid_account_id": plaid_account_id})
            if existing:
                await db.bankaccount.update(
                    where={"id": existing.id},
                    data={"current_balance_minor": plaid.plaid_amount_to_minor(current, currency)},
                )
            else:
                await db.bankaccount.create(data={
                    "tenant_id": tenant_id,
                    "plaid_account_id": plaid_account_id,
                    "plaid_item_id": item_id,
                    "name": acct.get("name", ""),
                    "type": acct.get("type", ""),
                    "subtype": acct.get("subtype", ""),
                    "current_balance_minor": plaid.plaid_amount_to_minor(current, currency),
                    "currency": currency,
                })
            accounts_synced += 1

        # Cursor-based transaction sync
        cursor = creds.get("sync_cursor")
        total_added = 0
        has_more = True

        while has_more:
            result = await plaid.sync_transactions(encrypted_access, cursor)

            for txn in result["added"]:
                txn_id = txn.get("transaction_id", "")
                amount = txn.get("amount", 0.0)
                currency = txn.get("iso_currency_code") or "USD"
                date_str = txn.get("date", "")
                if not txn_id or not date_str:
                    continue

                account = await db.bankaccount.find_unique(
                    where={"plaid_account_id": txn.get("account_id", "")}
                )
                if not account:
                    continue

                existing_txn = await db.banktransaction.find_unique(
                    where={"plaid_transaction_id": txn_id}
                )
                if not existing_txn:
                    await db.banktransaction.create(data={
                        "tenant_id": tenant_id,
                        "account_id": account.id,
                        "plaid_transaction_id": txn_id,
                        "amount_minor": plaid.plaid_amount_to_minor(amount, currency),
                        "currency": currency,
                        "merchant_name": txn.get("merchant_name"),
                        "description": txn.get("name", ""),
                        "date": datetime.fromisoformat(date_str),
                        "category": (txn.get("personal_finance_category") or {}).get("primary"),
                        "status": "pending",
                    })
                    total_added += 1

            cursor = result["next_cursor"]
            has_more = result["has_more"]

        # Persist updated cursor
        creds["sync_cursor"] = cursor
        await db.integration.update(
            where={"id": integration_id},
            data={"encrypted_credentials": json.dumps(creds)},
        )

        # Emit transaction_posted event for newly synced transactions
        if total_added > 0:
            try:
                from app.orchestrator.events import enqueue_orchestrator_event

                new_txns = await db.banktransaction.find_many(
                    where={"tenant_id": tenant_id, "status": "pending"},
                    take=total_added,
                    order={"created_at": "desc"},
                )
                if new_txns:
                    idempotency_key = f"plaid:sync:{integration_id}:{cursor[:24] if cursor else 'initial'}"
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="transaction_posted",
                        payload={"transaction_ids": [t.id for t in new_txns]},
                        idempotency_key=idempotency_key,
                        db=db,
                    )
            except Exception as exc:
                logger.error("plaid_sync_event_enqueue_failed", extra={"error": str(exc)})

        logger.info(
            "Plaid sync done: tenant=%s accounts=%d txns_added=%d",
            tenant_id,
            accounts_synced,
            total_added,
        )
        return {"status": "ok", "accounts_synced": accounts_synced, "transactions_added": total_added}

    except Exception as exc:
        logger.error("Plaid sync failed for integration %s: %s", integration_id, type(exc).__name__)
        return {"status": "error", "reason": type(exc).__name__}


async def reconcile_plaid_transactions(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    Reconciliation job: detects drift between Plaid transaction count and DB count.
    If drift detected, enqueues a full re-sync.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return {"status": "skipped"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on reconciliation — blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    creds = json.loads(integration.encrypted_credentials)
    encrypted_access = creds.get("access_token", "")

    try:
        # Count transactions in DB
        db_count = await db.banktransaction.count(where={"tenant_id": tenant_id})

        # Fetch one page from Plaid to compare
        result = await plaid.sync_transactions(encrypted_access, cursor=None)
        plaid_page_count = len(result["added"])

        logger.info(
            "Reconcile: tenant=%s db_txns=%d plaid_sample=%d",
            tenant_id,
            db_count,
            plaid_page_count,
        )

        if db_count == 0 and plaid_page_count > 0:
            logger.warning("Drift detected — DB empty but Plaid has transactions. Enqueuing re-sync.")
            await enqueue_plaid_sync(integration_id, tenant_id)
            return {"status": "resynced", "reason": "drift_detected"}

        return {"status": "ok", "db_count": db_count}

    except Exception as exc:
        logger.error("Plaid reconciliation failed: %s", type(exc).__name__)
        return {"status": "error", "reason": type(exc).__name__}


async def enqueue_plaid_sync(integration_id: str, tenant_id: str) -> None:
    import arq
    from app.core.config import get_settings
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_plaid_transactions", integration_id, tenant_id)
    await redis.aclose()
