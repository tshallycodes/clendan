"""
Microsoft OneDrive integration routes.
Handles OAuth connect flow, status, manual sync trigger, and disconnect.
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials
from app.integrations.onedrive import client as onedrive
from app.integrations.onedrive.sync import enqueue_onedrive_sync

logger = get_logger(__name__)
router = APIRouter(tags=["onedrive"])

INTEGRATION_TYPE = "onedrive"


@router.get("/integrations/onedrive/connect")
async def onedrive_connect(
    current_user: RequireOrgAuth,
):
    """Returns the Microsoft OAuth authorization URL for OneDrive."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = onedrive.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/onedrive/callback")
async def onedrive_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Microsoft identity platform for OneDrive.
    Exchanges code for tokens, stores encrypted credentials, enqueues sync.
    state format: {tenant_id}:{random}
    """
    parts = state.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state parameter")

    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    try:
        encrypted_creds_str = await onedrive.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("onedrive_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Microsoft token exchange failed")

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": encrypted_creds_str,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": INTEGRATION_TYPE,
                "encrypted_credentials": encrypted_creds_str,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_onedrive_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "onedrive_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )

    logger.info("onedrive_callback_ok tenant=%s integration_id=%s", tenant_id, integration.id)
    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.get("/integrations/onedrive/status")
async def onedrive_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the current OneDrive integration status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/onedrive/sync")
async def onedrive_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a OneDrive sync for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No OneDrive integration found")

    if integration.status not in ("connected", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sync not available in status: {integration.status}",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "syncing"},
    )

    try:
        await enqueue_onedrive_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error(
            "onedrive_manual_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync — queue may be unavailable",
        )

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.delete("/integrations/onedrive/disconnect")
async def onedrive_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Deletes the Graph API drive subscription, wipes credentials,
    and marks the integration as disconnected.
    """
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active OneDrive connection found")

    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            subscription_id = creds.get("subscription_id", "")
            access_token = creds.get("access_token", "")
            if subscription_id and access_token:
                await onedrive.delete_subscription(
                    access_token=access_token,
                    subscription_id=subscription_id,
                )
        except Exception as exc:
            logger.warning(
                "onedrive_subscription_delete_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("onedrive_disconnected tenant=%s integration_id=%s", current_user.tenant_id, integration.id)
    return standard_response(data={"status": "disconnected"})
