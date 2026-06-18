"""
Salesforce sync job — runs via arq worker.
Fetches accounts, contacts, opportunities, and contracts.
Writes a sync log entry per entity type.
"""
import time

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.salesforce import client as sf
from app.integrations.token_manager import get_valid_token

logger = get_logger(__name__)


async def sync_salesforce_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches accounts, contacts, opportunities, contracts from Salesforce.
    Writes a sync log entry per entity type.
    Updates integration status to "connected" on success, "error" on failure.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("salesforce_sync_skipped integration=%s reason=not_found", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("salesforce_sync_tenant_mismatch integration=%s — blocked", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status == "disconnected":
        logger.warning("salesforce_sync_skipped integration=%s reason=disconnected", integration_id)
        return {"status": "skipped", "reason": "disconnected"}

    try:
        access_token = await get_valid_token(integration_id, db)
    except Exception as exc:
        logger.error(
            "salesforce_token_fetch_failed integration=%s error=%s",
            integration_id,
            type(exc).__name__,
        )
        return {"status": "error", "reason": "token_unavailable"}

    # Retrieve instance_url from stored credentials
    import json
    raw_integration = await db.integration.find_unique(where={"id": integration_id})
    creds = json.loads(raw_integration.encrypted_credentials)
    try:
        instance_url = sf.get_instance_url(creds)
    except ValueError as exc:
        logger.error("salesforce_instance_url_missing integration=%s error=%s", integration_id, exc)
        return {"status": "error", "reason": "instance_url_missing"}

    results: dict = {}

    # --- Accounts ---
    accounts_start = time.monotonic()
    try:
        accounts = await sf.get_accounts(access_token, instance_url)
        elapsed_ms = int((time.monotonic() - accounts_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "success",
            "records_synced": len(accounts),
            "duration_ms": elapsed_ms,
        })
        results["accounts"] = len(accounts)
        logger.info("salesforce_accounts_synced tenant=%s count=%d", tenant_id, len(accounts))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - accounts_start) * 1000)
        logger.error("salesforce_accounts_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "accounts",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["accounts_error"] = type(exc).__name__

    # --- Contacts ---
    contacts_start = time.monotonic()
    try:
        contacts = await sf.get_contacts(access_token, instance_url)
        elapsed_ms = int((time.monotonic() - contacts_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "contacts",
            "status": "success",
            "records_synced": len(contacts),
            "duration_ms": elapsed_ms,
        })
        results["contacts"] = len(contacts)
        logger.info("salesforce_contacts_synced tenant=%s count=%d", tenant_id, len(contacts))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - contacts_start) * 1000)
        logger.error("salesforce_contacts_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "contacts",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["contacts_error"] = type(exc).__name__

    # --- Opportunities ---
    opps_start = time.monotonic()
    try:
        opportunities = await sf.get_opportunities(access_token, instance_url)
        elapsed_ms = int((time.monotonic() - opps_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "opportunities",
            "status": "success",
            "records_synced": len(opportunities),
            "duration_ms": elapsed_ms,
        })
        results["opportunities"] = len(opportunities)
        logger.info("salesforce_opportunities_synced tenant=%s count=%d", tenant_id, len(opportunities))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - opps_start) * 1000)
        logger.error("salesforce_opportunities_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "opportunities",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["opportunities_error"] = type(exc).__name__

    # --- Contracts ---
    contracts_start = time.monotonic()
    try:
        contracts = await sf.get_contracts(access_token, instance_url)
        elapsed_ms = int((time.monotonic() - contracts_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "contracts",
            "status": "success",
            "records_synced": len(contracts),
            "duration_ms": elapsed_ms,
        })
        results["contracts"] = len(contracts)
        logger.info("salesforce_contracts_synced tenant=%s count=%d", tenant_id, len(contracts))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - contracts_start) * 1000)
        logger.error("salesforce_contracts_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "contracts",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["contracts_error"] = type(exc).__name__

    # Re-read status — integration may have been disconnected while sync was running
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("salesforce_sync_aborted_disconnected integration=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    final_status = "error" if any(k.endswith("_error") for k in results) else "connected"
    await db.integration.update(
        where={"id": integration_id},
        data={"status": final_status},
    )

    logger.info("salesforce_sync_complete tenant=%s results=%s", tenant_id, results)
    return {"status": "ok", **results}


async def enqueue_salesforce_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Salesforce sync job onto the arq Redis queue."""
    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_salesforce_connection", integration_id, tenant_id)
