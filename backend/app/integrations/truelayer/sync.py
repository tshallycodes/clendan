"""
TrueLayer sync job — runs via arq tool.
Fetches accounts, balances, and 90-day transactions for a connected TrueLayer integration.
Writes BankAccount and BankTransaction records. Zero trust: validates before every DB write.
"""
from datetime import datetime, UTC, timedelta

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.truelayer import client as tl

logger = get_logger(__name__)

TRANSACTION_LOOKBACK_DAYS = 90


async def _dedup_truelayer_connections(db, integration_id: str, tenant_id: str) -> None:
    """
    After a successful sync, check if any older TrueLayer integration for this tenant has accounts
    that are all contained within the new integration. If so, delete the old integration.
    """
    new_accounts = await db.bankaccount.find_many(
        where={"integration_id": integration_id, "tenant_id": tenant_id}
    )
    new_ids = {a.truelayer_account_id for a in new_accounts if a.truelayer_account_id}
    if not new_ids:
        return

    other_integrations = await db.integration.find_many(
        where={
            "tenant_id": tenant_id,
            "type": "truelayer",
            "id": {"not": integration_id},
            "status": {"not": "disconnected"},
        }
    )

    for old_intg in other_integrations:
        old_accounts = await db.bankaccount.find_many(
            where={"integration_id": old_intg.id, "tenant_id": tenant_id}
        )
        old_ids = {a.truelayer_account_id for a in old_accounts if a.truelayer_account_id}
        if old_ids and old_ids.issubset(new_ids):
            await db.integrationsynclog.delete_many(where={"integration_id": old_intg.id})
            await db.bankaccount.update_many(
                where={"integration_id": old_intg.id},
                data={"integration_id": integration_id},
            )
            await db.integration.delete(where={"id": old_intg.id})
            logger.info(
                "TrueLayer dedup: removed duplicate integration %s (accounts reassigned to %s)",
                old_intg.id, integration_id,
            )


async def sync_truelayer_connection(_ctx: dict, integration_id: str, tenant_id: str) -> dict:
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("syncing", "connected"):
        logger.warning("TrueLayer sync skipped — integration %s not in expected state", integration_id)
        return {"status": "skipped", "reason": "not_syncing"}

    if integration.tenant_id != tenant_id:
        logger.error("Tenant mismatch on TrueLayer sync job — blocked (integration=%s)", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("TrueLayer credential decryption failed for integration %s", integration_id)
        return {"status": "error", "reason": "decryption_failed"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at", "")
    if token_expiry_at:
        expiry = datetime.fromisoformat(token_expiry_at)
        if datetime.now(UTC) >= expiry:
            try:
                new_tokens = await tl.refresh_truelayer_token(creds["refresh_token"])
                creds.update(new_tokens)
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
            except Exception as exc:
                logger.error("TrueLayer token refresh failed for integration %s: %s", integration_id, type(exc).__name__)
                await db.integration.update(where={"id": integration_id}, data={"status": "error"})
                return {"status": "error", "reason": "token_refresh_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        return {"status": "error", "reason": "missing_access_token"}

    # Fetch provider info and store institution_name if not already set
    try:
        provider_info = await tl.get_provider_info(access_token)
        provider = provider_info.get("provider") or {}
        institution_name = (
            provider.get("display_name")
            or provider.get("provider_id")
            or provider_info.get("provider_id")
        )
        if institution_name:
            await db.integration.update(
                where={"id": integration_id},
                data={"institution_name": institution_name},
            )
    except Exception:
        pass  # non-critical

    accounts_synced = 0
    total_transactions = 0

    try:
        sync_start = datetime.now(UTC)

        # --- Accounts + balances ---
        accounts = await tl.get_accounts(access_token)
        accounts_synced = len(accounts)

        from_date = (datetime.now(UTC) - timedelta(days=TRANSACTION_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        to_date = datetime.now(UTC).strftime("%Y-%m-%d")

        for account in accounts:
            tl_account_id = account.get("account_id", "")
            if not tl_account_id:
                continue

            # Fetch balance — required to upsert BankAccount
            try:
                balance_data = await tl.get_account_balance(access_token, tl_account_id)
                current_balance = balance_data.get("current", 0.0)
                balance_currency = balance_data.get("currency", "GBP")
            except Exception as exc:
                logger.warning("TrueLayer balance fetch failed for account %s: %s", tl_account_id, type(exc).__name__)
                current_balance = 0.0
                balance_currency = "GBP"

            # Upsert BankAccount
            balance_minor = round(abs(current_balance) * 100)
            existing_account = await db.bankaccount.find_first(
                where={"truelayer_account_id": tl_account_id}
            )
            if existing_account:
                await db.bankaccount.update(
                    where={"id": existing_account.id},
                    data={
                        "current_balance_minor": balance_minor,
                        "integration_id": integration_id,
                    },
                )
                db_account_id = existing_account.id
            else:
                created = await db.bankaccount.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "source": "truelayer",
                    "truelayer_account_id": tl_account_id,
                    "name": account.get("display_name") or account.get("account_type", "Account"),
                    "type": account.get("account_type", "transaction").lower(),
                    "subtype": account.get("account_subtype", ""),
                    "current_balance_minor": balance_minor,
                    "currency": balance_currency,
                })
                db_account_id = created.id

            await db.integrationsynclog.create(data={
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "entity_type": "balance",
                "status": "success",
                "records_synced": 1,
                "duration_ms": int((datetime.now(UTC) - sync_start).total_seconds() * 1000),
            })

            # --- Transactions ---
            try:
                txn_start = datetime.now(UTC)
                transactions = await tl.get_transactions(access_token, tl_account_id, from_date, to_date)
                txn_count = 0

                for txn in transactions:
                    tl_txn_id = txn.get("transaction_id", "")
                    if not tl_txn_id:
                        continue

                    # Validate required fields before writing
                    raw_amount = txn.get("amount")
                    txn_date = txn.get("timestamp") or txn.get("date", "")
                    if raw_amount is None or not txn_date:
                        continue

                    txn_currency = txn.get("currency", balance_currency)
                    # TrueLayer: negative = debit (money out), positive = credit (money in)
                    amount_minor = round(abs(float(raw_amount)) * 100)

                    try:
                        date_parsed = datetime.fromisoformat(txn_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue

                    existing_txn = await db.banktransaction.find_first(
                        where={"truelayer_transaction_id": tl_txn_id}
                    )
                    if not existing_txn:
                        await db.banktransaction.create(data={
                            "tenant_id": tenant_id,
                            "account_id": db_account_id,
                            "source": "truelayer",
                            "truelayer_transaction_id": tl_txn_id,
                            "amount_minor": amount_minor,
                            "currency": txn_currency,
                            "merchant_name": txn.get("merchant_name") or txn.get("normalised_provider_transaction_id"),
                            "description": txn.get("description", ""),
                            "date": date_parsed,
                            "category": txn.get("transaction_classification", [None])[0] if txn.get("transaction_classification") else None,
                            "status": "pending",
                        })
                        txn_count += 1

                total_transactions += txn_count
                txn_elapsed_ms = int((datetime.now(UTC) - txn_start).total_seconds() * 1000)
                await db.integrationsynclog.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "entity_type": "transactions",
                    "status": "success",
                    "records_synced": txn_count,
                    "duration_ms": txn_elapsed_ms,
                })

            except Exception as exc:
                logger.warning("TrueLayer transactions fetch failed for account %s: %s", tl_account_id, type(exc).__name__)
                await db.integrationsynclog.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "entity_type": "transactions",
                    "status": "error",
                    "records_synced": 0,
                    "duration_ms": 0,
                    "error_message": type(exc).__name__,
                })

        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "success",
            "records_synced": accounts_synced,
            "duration_ms": int((datetime.now(UTC) - sync_start).total_seconds() * 1000),
        })

        # Re-read status — integration may have been disconnected while sync was running
        current = await db.integration.find_unique(where={"id": integration_id})
        if not current or current.status == "disconnected":
            logger.info("TrueLayer sync aborted — integration %s was disconnected during run", integration_id)
            return {"status": "skipped", "reason": "disconnected_during_sync"}

        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "last_synced_at": datetime.now(UTC)},
        )

        # Emit orchestrator events for newly synced transactions
        if total_transactions > 0:
            try:
                from app.orchestrator.events import enqueue_orchestrator_event
                new_txns = await db.banktransaction.find_many(
                    where={"tenant_id": tenant_id, "source": "truelayer", "status": "pending"},
                    take=total_transactions,
                    order={"created_at": "desc"},
                )
                if new_txns:
                    txn_ids = [t.id for t in new_txns]
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="transaction_posted",
                        payload={"transaction_ids": txn_ids},
                        idempotency_key=f"truelayer:sync:{integration_id}:{from_date}",
                        db=db,
                    )
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="compliance_check_requested",
                        payload={"transaction_ids": txn_ids},
                        idempotency_key=f"truelayer:compliance:{integration_id}:{from_date}",
                        db=db,
                    )
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="treasury_run",
                        payload={},
                        idempotency_key=f"truelayer:treasury:{integration_id}:{from_date}",
                        db=db,
                    )
            except Exception as exc:
                logger.error("truelayer_sync_event_enqueue_failed", extra={"error": str(exc)})

        # Dedup: if an older integration has accounts that are all present in this one, delete it
        await _dedup_truelayer_connections(db, integration_id, tenant_id)

        logger.info(
            "TrueLayer sync done: tenant=%s accounts=%d transactions=%d",
            tenant_id, accounts_synced, total_transactions,
        )
        return {"status": "ok", "accounts_synced": accounts_synced, "transactions_synced": total_transactions}

    except Exception as exc:
        logger.error("TrueLayer sync failed for integration %s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": type(exc).__name__}


async def enqueue_truelayer_sync(integration_id: str, tenant_id: str) -> None:
    import arq
    from app.core.config import get_settings
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_truelayer_connection", integration_id, tenant_id)
    await redis.aclose()
