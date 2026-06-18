"""
Dropbox integration routes.
OAuth flow: connect → callback → enqueue sync.
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
from app.integrations.dropbox import client as dropbox
from app.integrations.dropbox.sync import enqueue_dropbox_sync

logger = get_logger(__name__)
router = APIRouter(tags=["dropbox"])

INTEGRATION_TYPE = "dropbox"


@router.get("/integrations/dropbox/connect")
async def dropbox_connect(
    current_user: RequireOrgAuth,
):
    """Returns Dropbox OAuth authorization URL and state token."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = dropbox.build_auth_url(state=state)
    return standard_response(data={"url": auth_url, "state": state})


@router.get("/integrations/dropbox/callback")
async def dropbox_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    Handles Dropbox OAuth callback.
    Exchanges code, stores encrypted credentials, enqueues sync.
    state format: {tenant_id}:{random}
    """
    parts = state.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    try:
        encrypted_creds_str = await dropbox.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("dropbox_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Dropbox token exchange failed")

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
        await enqueue_dropbox_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("dropbox_sync_enqueue_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.get("/integrations/dropbox/status")
async def dropbox_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Dropbox integration status for the tenant."""
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


@router.post("/integrations/dropbox/sync")
async def dropbox_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Dropbox sync for the tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Dropbox integration found")

    if integration.status not in ("connected", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot trigger sync — current status: {integration.status}",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "syncing"},
    )

    try:
        await enqueue_dropbox_sync(integration_id=integration.id, tenant_id=current_user.tenant_id)
    except Exception as exc:
        logger.error(
            "dropbox_manual_sync_enqueue_failed tenant=%s: %s",
            current_user.tenant_id, type(exc).__name__,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to enqueue Dropbox sync")

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.delete("/integrations/dropbox/disconnect")
async def dropbox_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Dropbox token and marks the integration as disconnected."""
    from app.integrations.encryption import decrypt_credentials

    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Dropbox integration found")

    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            access_token = creds.get("access_token", "")
            if access_token:
                try:
                    await dropbox.revoke_token(access_token)
                except Exception as exc:
                    logger.warning(
                        "dropbox_revoke_token_failed tenant=%s: %s",
                        current_user.tenant_id, type(exc).__name__,
                    )
        except ValueError:
            logger.warning(
                "dropbox_disconnect_decrypt_failed tenant=%s — proceeding with disconnect",
                current_user.tenant_id,
            )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
