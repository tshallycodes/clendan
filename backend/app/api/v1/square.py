"""Square Connect OAuth routes — connect, callback, status, sync, disconnect."""
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
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.square import client as square_client
from app.integrations.square.sync import enqueue_square_sync

logger = get_logger(__name__)
router = APIRouter(tags=["square"])


@router.get("/integrations/square/connect")
async def square_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the Square OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = square_client.build_square_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/square/callback")
async def square_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Square. Exchanges code for access_token,
    encrypts and stores credentials, sets status=syncing, enqueues sync job.
    Redirects to /dashboard/integrations?connected=square on success.
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter",
        )
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    try:
        tokens = await square_client.exchange_square_code(code=code)
    except Exception as exc:
        logger.error("Square OAuth code exchange failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Square token exchange failed",
        )

    encrypted = encrypt_credentials(tokens, tenant_id)

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "square"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "square",
                "encrypted_credentials": encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_square_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue Square sync after connect (will retry later): %s",
            type(exc).__name__,
        )

    return RedirectResponse(
        url="/dashboard/integrations?connected=square",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/integrations/square/status")
async def square_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Square integration status and connected_at for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "square"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": (
                integration.connected_at.isoformat() if integration.connected_at else None
            ),
            "integration_id": integration.id,
        }
    )


@router.post("/integrations/square/sync")
async def square_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Square sync job for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "square"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Square integration found",
        )

    try:
        await enqueue_square_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error("Failed to enqueue Square sync: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync job",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/square/disconnect")
async def square_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Square OAuth and marks the integration as disconnected."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "square"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Square integration found",
        )

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        access_token = creds.get("access_token", "")
        if access_token:
            await square_client.revoke_square_token(access_token)
    except Exception as exc:
        logger.warning(
            "Square token revocation failed (proceeding with local disconnect): %s",
            type(exc).__name__,
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
