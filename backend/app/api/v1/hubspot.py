"""
HubSpot OAuth integration routes.
Handles connect, callback, status, manual sync trigger, and disconnect.
No webhooks — HubSpot integration uses polling-based sync.
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials
from app.integrations.hubspot import client as hs
from app.integrations.hubspot.sync import enqueue_hubspot_sync

logger = get_logger(__name__)
router = APIRouter(tags=["hubspot"])


@router.get("/integrations/hubspot/connect")
async def hubspot_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the HubSpot OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = hs.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/hubspot/callback")
async def hubspot_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from HubSpot. Exchanges code for tokens, fetches portal info,
    stores encrypted credentials, enqueues initial sync.
    Redirects to /dashboard/integrations?connected=hubspot on success.
    All steps required — partial completion is a failure.
    """
    # Validate and extract tenant_id from state
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    tenant_id = parts[0]

    # Verify tenant exists (tenant isolation — never skip)
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Exchange code for tokens — returns encrypted credentials blob
    try:
        encrypted_blob = await hs.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("hubspot_token_exchange_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="HubSpot token exchange failed",
        )

    # Decrypt to get access_token for portal info fetch (zero trust confirmation)
    try:
        raw_creds = decrypt_credentials(encrypted_blob, tenant_id)
        access_token = raw_creds["access_token"]
    except Exception as exc:
        logger.error("hubspot_creds_decrypt_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Credential processing failed",
        )

    # Fetch portal info — confirms the token is live and retrieves portal_id
    try:
        portal_info = await hs.get_portal_info(access_token=access_token)
        portal_id = str(portal_info.get("hub_id", ""))
    except Exception as exc:
        logger.error("hubspot_portal_info_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch HubSpot portal info",
        )

    # Re-encrypt with portal_id merged in
    from app.integrations.encryption import encrypt_credentials
    final_creds = {
        "access_token": raw_creds["access_token"],
        "refresh_token": raw_creds["refresh_token"],
        "portal_id": portal_id,
        "token_expiry_at": raw_creds["token_expiry_at"],
    }
    credentials_blob = encrypt_credentials(final_creds, tenant_id)

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "hubspot"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": credentials_blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "hubspot",
                "encrypted_credentials": credentials_blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    logger.info(
        "hubspot_connected tenant=%s portal_id=%s integration=%s",
        tenant_id,
        portal_id,
        integration.id,
    )

    # Enqueue initial sync — non-fatal if queue is temporarily unavailable
    try:
        await enqueue_hubspot_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "hubspot_sync_enqueue_failed integration=%s error=%s (will retry later)",
            integration.id,
            type(exc).__name__,
        )

    return RedirectResponse(
        url="/dashboard/integrations?connected=hubspot",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/integrations/hubspot/status")
async def hubspot_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current HubSpot connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": (
                integration.connected_at.isoformat()
                if integration.connected_at
                else None
            ),
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/hubspot/sync")
async def hubspot_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a HubSpot sync job for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HubSpot connection found",
        )

    if integration.status not in ("connected", "syncing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot sync — integration status is '{integration.status}'",
        )

    try:
        await enqueue_hubspot_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error(
            "hubspot_manual_sync_enqueue_failed integration=%s error=%s",
            integration.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync — queue may be temporarily unavailable",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/hubspot/disconnect")
async def hubspot_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Wipes HubSpot credentials and marks integration as disconnected."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HubSpot connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info(
        "hubspot_disconnected tenant=%s integration=%s",
        current_user.tenant_id,
        integration.id,
    )

    return standard_response(data={"status": "disconnected"})
