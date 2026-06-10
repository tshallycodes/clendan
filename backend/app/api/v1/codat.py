"""
Codat integration routes.
Codat is a META-integration platform — one connection gives access to 50+ accounting platforms
(QuickBooks, Xero, Sage, FreshBooks, etc.) through a single unified API.

Connect flow (NOT standard OAuth):
  1. POST /integrations/codat/connect — creates Codat company, returns link_url
  2. User visits link_url in their browser to connect their accounting platform
  3. GET /integrations/codat/status — poll until connections appear (status → connected)
"""
import json
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.codat import client as codat
from app.integrations.codat.sync import enqueue_codat_sync
from app.integrations.encryption import decrypt_credentials, encrypt_credentials

logger = get_logger(__name__)
router = APIRouter(tags=["codat"])


@router.post("/integrations/codat/connect")
async def codat_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Creates a Codat company for the tenant and returns the Codat Link URL.
    The user MUST visit link_url to connect their accounting platform — this is not standard OAuth.
    Status is set to 'connecting' until the user completes the Link flow.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.codat_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Codat integration is not configured",
        )

    tenant_id = current_user.tenant_id

    # Resolve company name from tenant record
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    company_name = (tenant.name if tenant and tenant.name else f"tenant-{tenant_id}")

    try:
        company = await codat.create_company(tenant_id=tenant_id, company_name=company_name)
    except Exception as exc:
        logger.error("Codat create_company failed for tenant %s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Codat company",
        )

    company_id = company["id"]
    link_url = company["redirect"]

    encrypted = encrypt_credentials(
        {"company_id": company_id, "link_url": link_url},
        tenant_id,
    )

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "codat"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": encrypted,
                "status": "connecting",
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "codat",
                "encrypted_credentials": encrypted,
                "status": "connecting",
            }
        )

    logger.info(
        "Codat company created: tenant=%s integration=%s",
        tenant_id, integration.id,
    )

    return standard_response(
        data={
            "link_url": link_url,
            "company_id": company_id,
            "integration_id": integration.id,
            "note": "Visit link_url in your browser to connect your accounting platform. "
                    "Codat gives you access to 50+ platforms in one connection.",
        }
    )


@router.get("/integrations/codat/status")
async def codat_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Polls Codat for connection status. If connections exist, promotes to 'syncing' and enqueues sync.
    Poll this endpoint after directing the user to link_url.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.codat_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Codat integration is not configured",
        )

    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "codat"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        logger.error("Codat status credential decryption failed: tenant=%s", tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Integration credential error",
        )

    company_id = creds.get("company_id", "")
    link_url = creds.get("link_url", "")

    if not company_id:
        return standard_response(
            data={"status": integration.status, "link_url": link_url, "connections": []}
        )

    try:
        connections = await codat.get_company_connections(company_id)
    except Exception as exc:
        logger.error("Codat get_connections failed: %s", type(exc).__name__)
        return standard_response(
            data={"status": integration.status, "link_url": link_url, "connections": []}
        )

    active_connections = [c for c in connections if c.get("status") == "Linked"]

    if active_connections and integration.status == "connecting":
        integration = await db.integration.update(
            where={"id": integration.id},
            data={"status": "syncing"},
        )
        try:
            await enqueue_codat_sync(integration_id=integration.id, tenant_id=tenant_id)
        except Exception as exc:
            logger.warning(
                "Codat status enqueue_sync failed (will retry on next poll): %s",
                type(exc).__name__,
            )

    connection_summaries = [
        {
            "id": c.get("id"),
            "platform": c.get("platformName"),
            "status": c.get("status"),
        }
        for c in connections
    ]

    return standard_response(
        data={
            "status": integration.status,
            "connections": connection_summaries,
            "link_url": link_url,
        }
    )


@router.post("/integrations/codat/sync")
async def codat_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Enqueues a manual Codat sync job for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "codat"}
    )
    if not integration or integration.status not in ("syncing", "connected"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Codat connection to sync",
        )

    try:
        await enqueue_codat_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("Codat manual sync enqueue failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue sync job",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/codat/disconnect")
async def codat_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the Codat integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "codat"}
    )
    if not integration or integration.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Codat connection",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("Codat disconnected: tenant=%s integration=%s", tenant_id, integration.id)

    return standard_response(data={"status": "disconnected"})
