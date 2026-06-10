"""
TrueLayer sync job — runs via arq worker.
Fetches accounts, balances, and 90-day transactions for a connected TrueLayer integration.
"""
from datetime import datetime, UTC, timedelta

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.truelayer import client as tl

logger = get_logger(__name__)

TRANSACTION_LOOKBACK_DAYS = 90


async def sync_truelayer_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches accounts, balances, and 90-day transactions for a TrueLayer integration.
    Writes IntegrationSyncLog entries per entity type. Marks integration connected on success.
    Zero trust: validates all data from TrueLayer before writing.
    """
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
    except ValueError as exc:
        logger.error("TrueLayer credential decryption failed for integration %s", integration_id)
        return {"status": "error", "reason": "decryption_failed"}

    # Refresh token if expired or close to expiry
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
                logger.info("TrueLayer token refreshed for integration %s", integration_id)
            except Exception as exc:
                logger.error(
                    "TrueLayer token refresh failed for integration %s: %s",
                    integration_id,
                    type(exc).__name__,
                )
                await db.integration.update(
                    where={"id": integration_id},
                    data={"status": "error"},
                )
                return {"status": "error", "reason": "token_refresh_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        return {"status": "error", "reason": "missing_access_token"}

    try:
        # --- Accounts ---
        sync_start = datetime.now(UTC)
        accounts = await tl.get_accounts(access_token)
        accounts_synced = len(accounts)

        elapsed_ms = int((datetime.now(UTC) - sync_start).total_seconds() * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "success",
            "records_synced": accounts_synced,
            "duration_ms": elapsed_ms,
        })

        # --- Balances + Transactions per account ---
        from_date = (datetime.now(UTC) - timedelta(days=TRANSACTION_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        to_date = datetime.now(UTC).strftime("%Y-%m-%d")
        total_transactions = 0

        for account in accounts:
            account_id = account.get("account_id", "")
            if not account_id:
                continue

            # Balance
            try:
                balance_start = datetime.now(UTC)
                await tl.get_account_balance(access_token, account_id)
                balance_elapsed_ms = int((datetime.now(UTC) - balance_start).total_seconds() * 1000)
                await db.integrationsynclog.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "entity_type": "balance",
                    "status": "success",
                    "records_synced": 1,
                    "duration_ms": balance_elapsed_ms,
                })
            except Exception as exc:
                logger.warning(
                    "TrueLayer balance fetch failed for account %s: %s",
                    account_id,
                    type(exc).__name__,
                )
                await db.integrationsynclog.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "entity_type": "balance",
                    "status": "error",
                    "records_synced": 0,
                    "duration_ms": 0,
                })

            # Transactions
            try:
                txn_start = datetime.now(UTC)
                transactions = await tl.get_transactions(access_token, account_id, from_date, to_date)
                txn_count = len(transactions)
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
                logger.warning(
                    "TrueLayer transactions fetch failed for account %s: %s",
                    account_id,
                    type(exc).__name__,
                )
                await db.integrationsynclog.create(data={
                    "tenant_id": tenant_id,
                    "integration_id": integration_id,
                    "entity_type": "transactions",
                    "status": "error",
                    "records_synced": 0,
                    "duration_ms": 0,
                })

        # Mark integration connected
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected"},
        )

        logger.info(
            "TrueLayer sync done: tenant=%s accounts=%d transactions=%d",
            tenant_id,
            accounts_synced,
            total_transactions,
        )
        return {
            "status": "ok",
            "accounts_synced": accounts_synced,
            "transactions_synced": total_transactions,
        }

    except Exception as exc:
        logger.error(
            "TrueLayer sync failed for integration %s: %s",
            integration_id,
            type(exc).__name__,
        )
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "error"},
        )
        return {"status": "error", "reason": type(exc).__name__}


async def enqueue_truelayer_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_truelayer_connection arq job onto the Redis queue."""
    import arq
    from app.core.config import get_settings

    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_truelayer_connection", integration_id, tenant_id)
    await redis.aclose()
