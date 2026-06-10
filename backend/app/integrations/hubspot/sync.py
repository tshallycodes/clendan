"""
HubSpot sync job — runs via arq worker.
Fetches contacts, companies, and deals. Writes a sync log entry per entity type.
"""
import time

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.hubspot import client as hs
from app.integrations.token_manager import get_valid_token

logger = get_logger(__name__)


async def sync_hubspot_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: fetches contacts, companies, deals from HubSpot.
    Writes a sync log entry per entity type.
    Updates integration status to "connected" on success.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("hubspot_sync_skipped integration=%s reason=not_found", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("hubspot_sync_tenant_mismatch integration=%s — blocked", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    try:
        access_token = await get_valid_token(integration_id, db)
    except Exception as exc:
        logger.error("hubspot_token_fetch_failed integration=%s error=%s", integration_id, type(exc).__name__)
        return {"status": "error", "reason": "token_unavailable"}

    results: dict = {}

    # --- Contacts ---
    contacts_start = time.monotonic()
    try:
        contacts = await _fetch_all_pages(hs.get_contacts, access_token)
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
        logger.info("hubspot_contacts_synced tenant=%s count=%d", tenant_id, len(contacts))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - contacts_start) * 1000)
        logger.error("hubspot_contacts_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "contacts",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["contacts_error"] = type(exc).__name__

    # --- Companies ---
    companies_start = time.monotonic()
    try:
        companies = await _fetch_all_pages(hs.get_companies, access_token)
        elapsed_ms = int((time.monotonic() - companies_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "companies",
            "status": "success",
            "records_synced": len(companies),
            "duration_ms": elapsed_ms,
        })
        results["companies"] = len(companies)
        logger.info("hubspot_companies_synced tenant=%s count=%d", tenant_id, len(companies))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - companies_start) * 1000)
        logger.error("hubspot_companies_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "companies",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["companies_error"] = type(exc).__name__

    # --- Deals ---
    deals_start = time.monotonic()
    try:
        deals = await _fetch_all_pages(hs.get_deals, access_token)
        elapsed_ms = int((time.monotonic() - deals_start) * 1000)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "deals",
            "status": "success",
            "records_synced": len(deals),
            "duration_ms": elapsed_ms,
        })
        results["deals"] = len(deals)
        logger.info("hubspot_deals_synced tenant=%s count=%d", tenant_id, len(deals))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - deals_start) * 1000)
        logger.error("hubspot_deals_sync_failed integration=%s error=%s", integration_id, type(exc).__name__)
        await db.integrationsynclog.create(data={
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "entity_type": "deals",
            "status": "error",
            "records_synced": 0,
            "duration_ms": elapsed_ms,
        })
        results["deals_error"] = type(exc).__name__

    # Mark integration as connected after sync completes
    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected"},
    )

    logger.info("hubspot_sync_complete tenant=%s results=%s", tenant_id, results)
    return {"status": "ok", **results}


async def _fetch_all_pages(fetch_fn, access_token: str) -> list:
    """
    Paginates through all pages of a HubSpot CRM endpoint using cursor-based `after` param.
    Returns flat list of all result objects.
    """
    all_results: list = []
    after: str | None = None

    while True:
        page = await fetch_fn(access_token=access_token, after=after)
        results = page.get("results", [])
        all_results.extend(results)

        paging = page.get("paging")
        if not paging:
            break
        next_page = paging.get("next")
        if not next_page:
            break
        after = next_page.get("after")
        if not after:
            break

    return all_results


async def enqueue_hubspot_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a HubSpot sync job onto the arq Redis queue."""
    import arq
    from app.core.config import get_settings
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_hubspot_connection", integration_id, tenant_id)
    await redis.aclose()
