"""NetSuite integration routes - OAuth connect, status, sync, disconnect."""
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
from app.integrations.netsuite import client as netsuite
from app.integrations.netsuite.sync import enqueue_netsuite_sync

logger = get_logger(__name__)
router = APIRouter(tags=["netsuite"])


@router.get("/integrations/netsuite/connect")
async def netsuite_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns NetSuite OAuth URL. state encodes tenant_id for callback extraction."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = netsuite.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/netsuite/callback")
async def netsuite_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """OAuth callback - exchanges code, stores credentials, enqueues sync."""
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
        encrypted_creds_str = await netsuite.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error(
            "netsuite_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="NetSuite token exchange failed",
        )

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "netsuite"}
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
                "type": "netsuite",
                "encrypted_credentials": encrypted_creds_str,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_netsuite_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "netsuite_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )

    logger.info(
        "netsuite_callback_ok tenant=%s integration_id=%s",
        tenant_id, integration.id,
    )
    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.get("/integrations/netsuite/status")
async def netsuite_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "netsuite"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    account_id = ""
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            account_id = creds.get("account_id", "")
        except ValueError:
            pass

    connected_at = integration.connected_at.isoformat() if integration.connected_at else None
    last_synced_at = integration.last_synced_at.isoformat() if integration.last_synced_at else None
    return standard_response(data={
        "status": integration.status,
        "connected_at": connected_at,
        "last_synced_at": last_synced_at,
        "integration_id": integration.id,
        "account_id": account_id,
        "summary": integration.sync_metadata,
    })


@router.post("/integrations/netsuite/sync")
async def netsuite_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "netsuite"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No NetSuite integration found",
        )
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
        await enqueue_netsuite_sync(integration_id=integration.id, tenant_id=current_user.tenant_id)
    except Exception as exc:
        logger.error("netsuite_manual_sync_enqueue_failed integration_id=%s: %s", integration.id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to enqueue sync")

    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/netsuite/disconnect")
async def netsuite_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    integration = await db.integration.find_first(
        where={
            "tenant_id": current_user.tenant_id,
            "type": "netsuite",
            "status": {"not": "disconnected"},
        }
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active NetSuite connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info(
        "netsuite_disconnected tenant=%s integration_id=%s",
        current_user.tenant_id, integration.id,
    )
    return standard_response(data={"status": "disconnected"})
