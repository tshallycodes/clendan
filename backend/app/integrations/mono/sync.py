"""
Mono sync job — runs via arq worker.
Fetches and stores bank accounts + transactions for a connected Mono account.
"""
import json
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.mono import client as mono

logger = get_logger(__name__)


async def sync_mono_transactions(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: syncs account and transactions for a Mono integration.
    Zero trust: validates all data from Mono before writing to DB.
    Page-based pagination; deduplicates on mono_transaction_id.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status == "disconnected":
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on Mono sync — blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    creds = json.loads(integration.encrypted_credentials or "{}")
    encrypted_account_id = creds.get("account_id", "")
    if not encrypted_account_id:
        return {"status": "error", "reason": "missing_account_id"}

    _start = time.monotonic()

    try:
        # Sync account
        account_data = await mono.get_account(encrypted_account_id)
        balance_raw = account_data.get("balance", 0) or 0
        currency = account_data.get("currency", "NGN")
        institution = account_data.get("institution") or {}
        institution_name = institution.get("name", "")

        mono_acct_id_plain = account_data.get("id", "")
        existing_acct = await db.bankaccount.find_unique(
            where={"mono_account_id": mono_acct_id_plain}
        ) if mono_acct_id_plain else None

        raw_name = account_data.get("name", "") or account_data.get("type", "Account")
        account_name = f"{institution_name} - {raw_name}" if institution_name else raw_name

        if existing_acct:
            await db.bankaccount.update(
                where={"id": existing_acct.id},
                data={
                    "name": account_name,
                    "current_balance_minor": mono.mono_amount_to_minor(balance_raw, "debit"),
                    "integration_id": integration_id,
                },
            )
            account_db_id = existing_acct.id
        else:
            new_acct = await db.bankaccount.create(data={
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": "mono",
                "mono_account_id": mono_acct_id_plain,
                "name": account_name,
                "type": account_data.get("type", "").lower(),
                "subtype": institution.get("type", "").lower() or None,
                "current_balance_minor": mono.mono_amount_to_minor(balance_raw, "debit"),
                "currency": currency,
            })
            account_db_id = new_acct.id

        # Update institution name on the integration record
        if institution_name and integration.institution_name != institution_name:
            await db.integration.update(
                where={"id": integration_id},
                data={"institution_name": institution_name},
            )

        # Page-based transaction sync
        total_added = 0
        page = 1
        total_pages = 1

        while page <= total_pages:
            result = await mono.get_transactions(encrypted_account_id, page=page)
            meta = result.get("meta", {})
            total_pages = meta.get("pages", 1) or 1

            for txn in result["data"]:
                txn_id = txn.get("_id", "")
                if not txn_id:
                    continue

                existing_txn = await db.banktransaction.find_unique(
                    where={"mono_transaction_id": txn_id}
                )
                if existing_txn:
                    if existing_txn.status == "pending":
                        # Old sync hardcoded "pending" — Mono only returns settled txns
                        await db.banktransaction.update(
                            where={"id": existing_txn.id},
                            data={"status": "unprocessed"},
                        )
                    continue

                amount_raw = txn.get("amount", 0) or 0
                txn_type = txn.get("type", "debit")
                date_str = txn.get("date", "")
                if not date_str:
                    continue

                try:
                    txn_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    continue

                await db.banktransaction.create(data={
                    "tenant_id": tenant_id,
                    "account_id": account_db_id,
                    "source": "mono",
                    "mono_transaction_id": txn_id,
                    "amount_minor": mono.mono_amount_to_minor(amount_raw, txn_type),
                    "currency": currency,
                    "description": txn.get("narration", ""),
                    "category": txn.get("category"),
                    "date": txn_date,
                    "status": "unprocessed",
                })
                total_added += 1

            page += 1

        # Re-check integration status — it may have been disconnected during sync
        current = await db.integration.find_unique(where={"id": integration_id})
        if not current or current.status == "disconnected":
            logger.info("Mono sync aborted — integration %s disconnected during run", integration_id)
            return {"status": "skipped", "reason": "disconnected_during_sync"}

        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "last_synced_at": datetime.now(UTC)},
        )

        if total_added > 0:
            try:
                from app.orchestrator.events import enqueue_orchestrator_event

                new_txns = await db.banktransaction.find_many(
                    where={"tenant_id": tenant_id, "source": "mono", "status": {"in": ["pending", "unprocessed"]}},
                    take=total_added,
                    order={"created_at": "desc"},
                )
                if new_txns:
                    txn_ids = [t.id for t in new_txns]
                    sync_key = f"p{page}"
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="compliance_check_requested",
                        payload={"transaction_ids": txn_ids},
                        idempotency_key=f"mono:compliance:{integration_id}:{sync_key}",
                        db=db,
                    )
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="treasury_run",
                        payload={},
                        idempotency_key=f"mono:treasury:{integration_id}:{sync_key}",
                        db=db,
                    )
            except Exception as exc:
                logger.error("mono_sync_event_enqueue_failed: %s", type(exc).__name__)

        elapsed_ms = int((time.monotonic() - _start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "success",
            "records_synced": 1,
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

        logger.info(
            "Mono sync done: tenant=%s txns_added=%d",
            tenant_id,
            total_added,
        )
        return {"status": "ok", "accounts_synced": 1, "transactions_added": total_added}

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - _start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transactions",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
            "error_message": type(exc).__name__,
        })
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "error"},
        )
        logger.error("Mono sync failed for integration %s: %s", integration_id, type(exc).__name__)
        return {"status": "error", "reason": type(exc).__name__}


async def reconcile_mono_transactions(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    Reconciliation job: detects drift between Mono and DB transaction count.
    If DB is empty but Mono has data, enqueues a full re-sync.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return {"status": "skipped"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on Mono reconciliation — blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    creds = json.loads(integration.encrypted_credentials or "{}")
    encrypted_account_id = creds.get("account_id", "")

    try:
        db_count = await db.banktransaction.count(
            where={"tenant_id": tenant_id, "source": "mono"}
        )
        result = await mono.get_transactions(encrypted_account_id, page=1)
        mono_total = result.get("meta", {}).get("total", 0)

        logger.info(
            "Mono reconcile: tenant=%s db_txns=%d mono_total=%d",
            tenant_id, db_count, mono_total,
        )

        if db_count == 0 and mono_total > 0:
            logger.warning("Mono drift detected — DB empty but Mono has transactions. Re-syncing.")
            await enqueue_mono_sync(integration_id, tenant_id)
            return {"status": "resynced", "reason": "drift_detected"}

        return {"status": "ok", "db_count": db_count, "mono_total": mono_total}

    except Exception as exc:
        logger.error("Mono reconciliation failed: %s", type(exc).__name__)
        return {"status": "error", "reason": type(exc).__name__}


async def enqueue_mono_sync(integration_id: str, tenant_id: str) -> None:
    import arq
    from app.core.config import get_settings
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_mono_transactions", integration_id, tenant_id)
    await redis.aclose()
