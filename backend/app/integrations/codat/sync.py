"""
Codat sync jobs — run via arq tool.
Polls Codat for active connections, fetches invoices, writes sync logs.
"""
import json
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.codat import client as codat
from app.integrations.encryption import decrypt_credentials

logger = get_logger(__name__)


async def sync_codat_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: polls Codat for active connections, fetches invoices, writes sync logs.
    Tenant isolation enforced — mismatch aborts with error.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("Codat sync skipped — integration %s not found", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("Codat sync tenant mismatch — data leakage attempt blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "Codat sync skipped — integration %s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "not_syncing"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("Codat credential decryption failed for integration %s", integration_id)
        return {"status": "error", "reason": "credential_decryption_failed"}

    company_id = creds.get("company_id", "")
    if not company_id:
        logger.error("Codat sync missing company_id for integration %s", integration_id)
        return {"status": "error", "reason": "missing_company_id"}

    start_ms = datetime.now(UTC).timestamp() * 1000

    try:
        connections = await codat.get_company_connections(company_id)
    except Exception as exc:
        logger.error("Codat get_connections failed for integration %s: %s", integration_id, type(exc).__name__)
        return {"status": "error", "reason": "connections_fetch_failed"}

    active_connections = [c for c in connections if c.get("status") == "Linked"]
    if not active_connections:
        logger.info("Codat sync: no active connections for integration %s", integration_id)
        return {"status": "ok", "invoices_synced": 0, "connections": 0}

    total_invoices = 0
    errors = []

    for connection in active_connections:
        connection_id = connection.get("id", "")
        platform_name = connection.get("platformName", "unknown")
        if not connection_id:
            continue

        try:
            invoices = await codat.list_invoices(company_id, connection_id)
        except Exception as exc:
            logger.error(
                "Codat invoice fetch failed for connection %s (%s): %s",
                connection_id, platform_name, type(exc).__name__,
            )
            errors.append({"connection_id": connection_id, "error": type(exc).__name__})
            continue

        total_invoices += len(invoices)
        logger.info(
            "Codat fetched %d invoices from %s (connection=%s)",
            len(invoices), platform_name, connection_id,
        )

    elapsed_ms = int(datetime.now(UTC).timestamp() * 1000 - start_ms)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "entity_type": "invoices",
        "status": "error" if errors and total_invoices == 0 else "success",
        "records_synced": total_invoices,
        "duration_ms": elapsed_ms,
    })

    if total_invoices > 0:
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected"},
        )

    logger.info(
        "Codat sync complete: tenant=%s invoices=%d elapsed_ms=%d",
        tenant_id, total_invoices, elapsed_ms,
    )
    return {"status": "ok", "invoices_synced": total_invoices, "connections": len(active_connections)}


async def poll_codat_status(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: checks if user has completed the Codat Link flow.
    Updates status to 'syncing' and enqueues a full sync when connections are present.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("Codat poll skipped — integration %s not found", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("Codat poll tenant mismatch — blocked")
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status != "connecting":
        # Already progressed past connecting — nothing to poll
        return {"status": "skipped", "reason": "already_progressed"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("Codat poll credential decryption failed for integration %s", integration_id)
        return {"status": "error", "reason": "credential_decryption_failed"}

    company_id = creds.get("company_id", "")
    if not company_id:
        return {"status": "error", "reason": "missing_company_id"}

    try:
        connections = await codat.get_company_connections(company_id)
    except Exception as exc:
        logger.error("Codat poll connections failed: %s", type(exc).__name__)
        return {"status": "pending", "reason": "connections_fetch_failed"}

    active_connections = [c for c in connections if c.get("status") == "Linked"]
    if not active_connections:
        logger.info("Codat poll: user has not completed Link flow yet (integration=%s)", integration_id)
        return {"status": "pending", "connections": 0}

    # User completed Link flow — promote to syncing
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "syncing"},
    )

    await enqueue_codat_sync(integration_id=integration_id, tenant_id=tenant_id)

    logger.info(
        "Codat poll: %d connection(s) found, enqueued sync for integration %s",
        len(active_connections), integration_id,
    )
    return {"status": "syncing", "connections": len(active_connections)}


async def enqueue_codat_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a sync_codat_connection arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_codat_connection", integration_id, tenant_id)
    await redis.aclose()
