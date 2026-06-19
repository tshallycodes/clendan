"""
Plaid sync job — runs via arq tool.
Fetches and stores bank accounts + transactions for a connected Plaid item.
"""
import json
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.plaid import client as plaid

logger = get_logger(__name__)


async def _dedup_plaid_connections(db, integration_id: str, tenant_id: str) -> None:
    """
    After a successful sync, check if any older Plaid integration for this tenant has accounts
    that are all contained within the new integration. If so, the new connection is a superset
    (or same bank reconnected) — delete the old integration and reassign its sync logs.
    """
    new_accounts = await db.bankaccount.find_many(
        where={"integration_id": integration_id, "tenant_id": tenant_id}
    )
    new_ids = {a.plaid_account_id for a in new_accounts if a.plaid_account_id}
    logger.info("plaid_dedup_start integration_id=%s new_account_ids=%s", integration_id, new_ids)

    other_integrations = await db.integration.find_many(
        where={
            "tenant_id": tenant_id,
            "type": "plaid",
            "id": {"not": integration_id},
            "status": {"not": "disconnected"},
        }
    )
    logger.info("plaid_dedup_candidates integration_id=%s count=%d", integration_id, len(other_integrations))

    for old_intg in other_integrations:
        old_accounts = await db.bankaccount.find_many(
            where={"integration_id": old_intg.id, "tenant_id": tenant_id}
        )
        old_ids = {a.plaid_account_id for a in old_accounts if a.plaid_account_id}
        logger.info("plaid_dedup_check old_id=%s old_status=%s old_account_ids=%s is_subset=%s",
            old_intg.id, old_intg.status, old_ids, old_ids.issubset(new_ids))
        if old_ids.issubset(new_ids):  # empty set is subset of any set — cleans up orphaned failed attempts
            # Old integration's accounts are fully covered — clean it up
            await db.integrationsynclog.delete_many(where={"integration_id": old_intg.id})
            await db.bankaccount.update_many(
                where={"integration_id": old_intg.id},
                data={"integration_id": integration_id},
            )
            await db.integration.delete(where={"id": old_intg.id})
            logger.info("plaid_dedup_removed old_id=%s accounts_reassigned_to=%s", old_intg.id, integration_id)


async def sync_plaid_transactions(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: syncs all transactions for a Plaid integration.
    Uses cursor-based pagination. Stores accounts + transactions in DB.
    Zero trust: validates all data from Plaid before writing.
    """
    logger.info("plaid_sync_started integration_id=%s tenant_id=%s", integration_id, tenant_id)
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("syncing", "connected"):
        logger.warning("plaid_sync_skipped reason=not_in_syncable_state integration_id=%s status=%s", integration_id, integration.status if integration else "NOT_FOUND")
        return {"status": "skipped", "reason": "not_connected"}

    logger.info("plaid_sync_integration_ok integration_id=%s status=%s institution_name=%s", integration_id, integration.status, integration.institution_name)

    if integration.tenant_id != tenant_id:
        logger.error("plaid_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    creds = json.loads(integration.encrypted_credentials)
    encrypted_access = creds.get("access_token", "")
    item_id = creds.get("item_id", "")
    logger.info("plaid_sync_creds_check integration_id=%s has_access_token=%s has_item_id=%s", integration_id, bool(encrypted_access), bool(item_id))

    if not encrypted_access or not item_id:
        logger.error("plaid_sync_incomplete_creds integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "incomplete_credentials"}

    try:
        _start = time.monotonic()
        # Sync accounts first
        logger.info("plaid_sync_fetching_accounts integration_id=%s", integration_id)
        accounts_data = await plaid.get_accounts(encrypted_access)
        logger.info("plaid_sync_accounts_received integration_id=%s count=%d", integration_id, len(accounts_data))
        accounts_synced = 0
        for acct in accounts_data:
            plaid_account_id = acct.get("account_id", "")
            if not plaid_account_id:
                logger.warning("plaid_sync_account_no_id integration_id=%s acct=%s", integration_id, acct)
                continue
            balance = acct.get("balances", {})
            current = balance.get("current") or 0.0
            currency = balance.get("iso_currency_code") or "USD"
            logger.info("plaid_sync_account integration_id=%s plaid_account_id=%s name=%s type=%s balance=%s currency=%s",
                integration_id, plaid_account_id, acct.get("name"), acct.get("type"), current, currency)

            existing = await db.bankaccount.find_unique(where={"plaid_account_id": plaid_account_id})
            if existing:
                await db.bankaccount.update(
                    where={"id": existing.id},
                    data={
                        "current_balance_minor": plaid.plaid_amount_to_minor(current, currency),
                        "integration_id": integration_id,
                    },
                )
                logger.info("plaid_sync_account_updated db_id=%s plaid_account_id=%s", existing.id, plaid_account_id)
            else:
                created = await db.bankaccount.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "plaid_account_id": plaid_account_id,
                    "plaid_item_id": item_id,
                    "name": acct.get("name", ""),
                    "type": acct.get("type", ""),
                    "subtype": acct.get("subtype", ""),
                    "current_balance_minor": plaid.plaid_amount_to_minor(current, currency),
                    "currency": currency,
                })
                logger.info("plaid_sync_account_created db_id=%s plaid_account_id=%s", created.id, plaid_account_id)
            accounts_synced += 1

        logger.info("plaid_sync_accounts_done integration_id=%s accounts_synced=%d", integration_id, accounts_synced)

        # Cursor-based transaction sync
        cursor = creds.get("sync_cursor")
        total_added = 0
        has_more = True
        page = 0
        logger.info("plaid_sync_transactions_start integration_id=%s cursor=%s", integration_id, cursor[:12] if cursor else None)

        while has_more:
            result = await plaid.sync_transactions(encrypted_access, cursor)
            page += 1
            logger.info("plaid_sync_txn_page integration_id=%s page=%d added=%d has_more=%s", integration_id, page, len(result.get("added", [])), result.get("has_more"))

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

        logger.info("plaid_sync_transactions_done integration_id=%s total_added=%d pages=%d", integration_id, total_added, page)

        # Re-read status — integration may have been disconnected while sync was running
        current = await db.integration.find_unique(where={"id": integration_id})
        if not current or current.status == "disconnected":
            logger.info("plaid_sync_aborted reason=disconnected_during_sync integration_id=%s", integration_id)
            return {"status": "skipped", "reason": "disconnected_during_sync"}

        # Persist updated cursor + mark connected
        creds["sync_cursor"] = cursor
        await db.integration.update(
            where={"id": integration_id},
            data={"encrypted_credentials": json.dumps(creds), "status": "connected", "last_synced_at": datetime.now(UTC)},
        )
        logger.info("plaid_sync_status_connected integration_id=%s", integration_id)

        # Emit orchestrator events for newly synced transactions
        if total_added > 0:
            try:
                from app.orchestrator.events import enqueue_orchestrator_event

                new_txns = await db.banktransaction.find_many(
                    where={"tenant_id": tenant_id, "status": "pending"},
                    take=total_added,
                    order={"created_at": "desc"},
                )
                if new_txns:
                    txn_ids = [t.id for t in new_txns]
                    sync_key = cursor[:24] if cursor else "initial"
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="transaction_posted",
                        payload={"transaction_ids": txn_ids},
                        idempotency_key=f"plaid:sync:{integration_id}:{sync_key}",
                        db=db,
                    )
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="compliance_check_requested",
                        payload={"transaction_ids": txn_ids},
                        idempotency_key=f"plaid:compliance:{integration_id}:{sync_key}",
                        db=db,
                    )
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="treasury_run",
                        payload={},
                        idempotency_key=f"plaid:treasury:{integration_id}:{sync_key}",
                        db=db,
                    )
            except Exception as exc:
                logger.error("plaid_sync_event_enqueue_failed", extra={"error": str(exc)})

        elapsed_ms = int((time.monotonic() - _start) * 1000)

        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "success",
            "records_synced": accounts_synced,
            "duration_ms": elapsed_ms // 2,
        })
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transactions",
            "status": "success",
            "records_synced": total_added,
            "duration_ms": elapsed_ms // 2,
        })
        # Dedup: if an older integration has accounts that are all present in this one, delete it
        await _dedup_plaid_connections(db, integration_id, tenant_id)

        logger.info("plaid_sync_ok integration_id=%s accounts=%d txns_added=%d", integration_id, accounts_synced, total_added)
        return {"status": "ok", "accounts_synced": accounts_synced, "transactions_added": total_added}

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - _start) * 1000)
        _body = ""
        try:
            import httpx as _httpx
            if isinstance(exc, _httpx.HTTPStatusError):
                _body = exc.response.text[:500]
        except Exception:
            pass
        logger.error("plaid_sync_failed integration_id=%s exc=%s msg=%s body=%s elapsed_ms=%d", integration_id, type(exc).__name__, str(exc)[:200], _body, elapsed_ms, exc_info=True)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transactions",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
            "error_message": type(exc).__name__,
        })
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
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_plaid_transactions", integration_id, tenant_id)
    await redis.aclose()
