"""
Salesforce OAuth integration routes.
Handles connect, callback, status, manual sync trigger, and disconnect.
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
from app.integrations.salesforce import client as sf
from app.integrations.salesforce.sync import enqueue_salesforce_sync

logger = get_logger(__name__)
router = APIRouter(tags=["salesforce"])


@router.get("/integrations/salesforce/connect")
async def salesforce_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the Salesforce OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = sf.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/salesforce/callback")
async def salesforce_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback. Exchanges code for tokens (includes instance_url),
    stores encrypted credentials, enqueues initial sync.
    Does not require auth — tenant_id parsed from state parameter.
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    try:
        encrypted_blob = await sf.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("salesforce_token_exchange_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Salesforce token exchange failed")

    existing = await db.integration.find_first(where={"tenant_id": tenant_id, "type": "salesforce"})
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={"encrypted_credentials": encrypted_blob, "status": "syncing", "connected_at": datetime.now(UTC)},
        )
    else:
        integration = await db.integration.create(data={
            "tenant_id": tenant_id,
            "type": "salesforce",
            "encrypted_credentials": encrypted_blob,
            "status": "syncing",
            "connected_at": datetime.now(UTC),
        })

    logger.info("salesforce_connected tenant=%s integration=%s", tenant_id, integration.id)

    try:
        await enqueue_salesforce_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "salesforce_sync_enqueue_failed integration=%s error=%s (will retry later)",
            integration.id, type(exc).__name__,
        )

    return RedirectResponse(url="/dashboard/integrations?connected=salesforce", status_code=status.HTTP_302_FOUND)


@router.get("/integrations/salesforce/status")
async def salesforce_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current Salesforce connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "salesforce"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})
    return standard_response(data={
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "integration_id": integration.id,
    })


@router.post("/integrations/salesforce/sync")
async def salesforce_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Salesforce sync job for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "salesforce"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Salesforce connection found")
    if integration.status not in ("connected", "syncing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot sync — integration status is '{integration.status}'",
        )
    try:
        await enqueue_salesforce_sync(integration_id=integration.id, tenant_id=current_user.tenant_id)
    except Exception as exc:
        logger.error("salesforce_manual_sync_enqueue_failed integration=%s error=%s", integration.id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync — queue may be temporarily unavailable",
        )
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/salesforce/disconnect")
async def salesforce_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Salesforce token and marks integration as disconnected."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "salesforce", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Salesforce connection found")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
        if creds.get("access_token"):
            await sf.revoke_token(creds["access_token"])
    except Exception as exc:
        logger.warning("salesforce_revoke_failed integration=%s error=%s (continuing)", integration.id, type(exc).__name__)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    logger.info("salesforce_disconnected tenant=%s integration=%s", current_user.tenant_id, integration.id)
    return standard_response(data={"status": "disconnected"})
