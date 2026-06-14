"""
Sage Accounting OAuth integration routes.
Flow: connect → callback → sync → status / disconnect
"""
import secrets
import urllib.parse
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import encrypt_credentials
from app.integrations.sage import client as sage
from app.integrations.sage.sync import enqueue_sage_sync

logger = get_logger(__name__)
router = APIRouter(tags=["sage"])

_AUTH_URL = "https://www.sageone.com/oauth2/auth"
_SCOPE = "readonly"


@router.get("/integrations/sage/connect")
async def sage_connect(current_user: RequireOrgAuth):
    """Returns the Sage OAuth authorization URL. Frontend redirects the user there."""
    settings = get_settings()
    if not settings.sage_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sage OAuth credentials are not configured on this server",
        )

    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    params = {
        "client_id": settings.sage_client_id,
        "response_type": "code",
        "redirect_uri": settings.sage_redirect_uri,
        "scope": _SCOPE,
        "state": state,
    }
    auth_url = _AUTH_URL + "?" + urllib.parse.urlencode(params)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/sage/callback")
async def sage_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Sage.
    1. Validates state, extracts tenant_id.
    2. Exchanges code for tokens.
    3. Stores encrypted credentials, enqueues sync.
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    try:
        tokens = await sage.exchange_code(code)
    except Exception as exc:
        logger.error("sage_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Sage token exchange failed")

    blob = encrypt_credentials(tokens, tenant_id)

    existing = await db.integration.find_first(where={"tenant_id": tenant_id, "type": "sage"})
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={"encrypted_credentials": blob, "status": "syncing", "connected_at": datetime.now(UTC)},
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "sage",
                "encrypted_credentials": blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_sage_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("sage_enqueue_sync_failed: %s", type(exc).__name__)

    frontend_url = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/integrations?connected=sage",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/integrations/sage/status")
async def sage_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current Sage connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "sage"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(data={
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "integration_id": integration.id,
    })


@router.post("/integrations/sage/sync")
async def sage_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Enqueues a Sage sync job for the authenticated tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "sage", "status": "connected"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Sage connection found")

    try:
        await enqueue_sage_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("sage_manual_sync_enqueue_failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue sync job")

    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/sage/disconnect")
async def sage_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks Sage integration as disconnected and wipes credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "sage"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Sage connection found")

    logger.info("sage_disconnected tenant=%s integration_id=%s", tenant_id, integration.id)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
