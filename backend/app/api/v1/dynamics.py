"""Microsoft Dynamics 365 integration routes - OAuth connect, status, sync, disconnect."""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.dynamics import client as dynamics
from app.integrations.dynamics.sync import enqueue_dynamics_sync
from app.integrations.encryption import decrypt_credentials, encrypt_credentials

logger = get_logger(__name__)
router = APIRouter(tags=["dynamics"])


@router.get("/integrations/dynamics/connect")
async def dynamics_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    org_url: str = Query(..., description="Your Dynamics 365 org URL e.g. https://yourorg.crm.dynamics.com"),
):
    """Returns Microsoft OAuth authorization URL. State encodes tenant_id:org_url:nonce."""
    state = f"{current_user.tenant_id}:{org_url}:{secrets.token_urlsafe(16)}"
    auth_url = dynamics.build_auth_url(state=state, dynamics_org_url=org_url)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/dynamics/callback")
async def dynamics_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """OAuth callback - exchanges code for tokens, upserts integration, enqueues sync."""
    parts = state.split(":", 2)
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter",
        )
    tenant_id, org_url, _nonce = parts

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    try:
        encrypted_creds_str = await dynamics.exchange_code(
            code=code, tenant_id=tenant_id, dynamics_org_url=org_url
        )
    except Exception as exc:
        logger.error("dynamics_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft token exchange failed",
        )

    # Ensure org_url is stored in credentials
    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
        creds["dynamics_org_url"] = org_url
        encrypted_creds_str = encrypt_credentials(creds, tenant_id)
    except Exception as exc:
        logger.warning("dynamics_creds_update_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "dynamics"}
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
                "type": "dynamics",
                "encrypted_credentials": encrypted_creds_str,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_dynamics_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "dynamics_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )

    logger.info(
        "dynamics_callback_ok tenant=%s integration_id=%s org_url=%s",
        tenant_id, integration.id, org_url,
    )
    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "org_url": org_url,
        }
    )


@router.get("/integrations/dynamics/status")
async def dynamics_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the current Dynamics 365 integration status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "dynamics"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    org_url = ""
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            org_url = creds.get("dynamics_org_url", "")
        except ValueError:
            pass

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": (
                integration.connected_at.isoformat() if integration.connected_at else None
            ),
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "org_url": org_url,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/dynamics/sync")
async def dynamics_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Dynamics 365 sync for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={
            "tenant_id": current_user.tenant_id,
            "type": "dynamics",
            "status": {"not": "disconnected"},
        }
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Dynamics 365 integration found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "syncing"},
    )

    try:
        await enqueue_dynamics_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error(
            "dynamics_manual_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync - queue may be unavailable",
        )

    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/dynamics/disconnect")
async def dynamics_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Wipes credentials and marks the Dynamics 365 integration as disconnected."""
    integration = await db.integration.find_first(
        where={
            "tenant_id": current_user.tenant_id,
            "type": "dynamics",
            "status": {"not": "disconnected"},
        }
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Dynamics 365 connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info(
        "dynamics_disconnected tenant=%s integration_id=%s",
        current_user.tenant_id, integration.id,
    )
    return standard_response(data={"status": "disconnected"})
