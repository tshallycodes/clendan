"""
Wise sync job — runs via arq worker.
Fetches transfers for all connected Wise profiles.
Writes sync log entries per entity type.
"""
import time

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.wise import client as wise

logger = get_logger(__name__)

PROFILE_TYPE_BUSINESS = "BUSINESS"


async def sync_wise_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches transfers for a Wise integration.
    Writes a sync log entry for each profile's transfer fetch.
    Zero trust: validates all data from Wise before writing.
    Race condition guard: re-reads integration status before final write.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status not in ("connected", "syncing"):
        logger.warning(
            "Wise sync skipped — integration %s not in syncable state",
            integration_id,
        )
        return {"status": "skipped", "reason": "not_connected"}

    if integration.tenant_id != tenant_id:
        logger.error(
            "Tenant mismatch on Wise sync job — possible data leakage attempt blocked"
        )
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error(
            "Wise credential decryption failed for integration %s", integration_id
        )
        return {"status": "error", "reason": "credential_decryption_failed"}

    api_token = creds.get("api_token", "")
    environment = creds.get("environment", "sandbox")
    profile_id = creds.get("profile_id")

    if not api_token:
        return {"status": "error", "reason": "missing_api_token"}

    # Validate token and fetch profiles to resolve profile_id if not stored
    try:
        profiles = await wise.validate_api_token(api_token, environment)
    except Exception as exc:
        logger.error(
            "Wise token validation failed for integration %s: %s",
            integration_id,
            type(exc).__name__,
        )
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "error"},
        )
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "connection",
            "status": "error",
            "records_synced": 0,
            "duration_ms": 0,
        })
        return {"status": "error", "reason": type(exc).__name__}

    # Resolve profile_id — prefer the first BUSINESS profile, fall back to first profile
    if not profile_id:
        business_profiles = [p for p in profiles if p.get("type") == PROFILE_TYPE_BUSINESS]
        chosen = business_profiles[0] if business_profiles else profiles[0]
        profile_id = chosen["id"]
        logger.info(
            "Wise profile_id resolved: tenant=%s profile_id=%s type=%s",
            tenant_id,
            profile_id,
            chosen.get("type"),
        )

    results: dict = {}
    overall_status = "ok"
    total_transfers = 0

    # Sync transfers for the resolved profile
    transfers_start = time.monotonic()
    try:
        transfers = await wise.fetch_transfers(api_token, environment, profile_id)
        transfers_ms = int((time.monotonic() - transfers_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transfers",
            "status": "success",
            "records_synced": len(transfers),
            "duration_ms": transfers_ms,
        })
        total_transfers += len(transfers)
        results["transfers"] = total_transfers
        logger.info(
            "Wise transfers synced: tenant=%s profile_id=%s count=%d",
            tenant_id,
            profile_id,
            len(transfers),
        )
    except Exception as exc:
        overall_status = "partial"
        transfers_ms = int((time.monotonic() - transfers_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "transfers",
            "status": "error",
            "records_synced": 0,
            "duration_ms": transfers_ms,
        })
        results["transfers_error"] = type(exc).__name__
        logger.error(
            "Wise transfers sync failed: profile_id=%s error=%s",
            profile_id,
            type(exc).__name__,
        )

    # Race condition guard — re-read before final status write
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info(
            "Wise sync aborted — integration %s was disconnected during run",
            integration_id,
        )
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    # Persist profile_id back into encrypted credentials if it was newly resolved
    updated_creds = {**creds, "profile_id": profile_id}
    encrypted = encrypt_credentials(updated_creds, tenant_id)

    await db.integration.update(
        where={"id": integration_id},
        data={
            "status": "connected",
            "encrypted_credentials": encrypted,
        },
    )

    return {"status": overall_status, "transfers": total_transfers}


async def enqueue_wise_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Wise sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_wise_connection", integration_id, tenant_id)
    await redis.aclose()
