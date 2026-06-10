import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.truelayer import client as tl
from app.integrations.truelayer.sync import enqueue_truelayer_sync

logger = get_logger(__name__)
router = APIRouter(tags=["truelayer"])


@router.get("/integrations/truelayer/connect")
async def truelayer_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns a TrueLayer OAuth authorisation URL. The frontend redirects the user there."""
    tenant_id = current_user.tenant_id
    random_part = secrets.token_urlsafe(16)
    state = f"{tenant_id}:{random_part}"
    auth_url = tl.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/truelayer/callback")
async def truelayer_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Annotated[Prisma, Depends(get_db_dep)] = None,
):
    """
    OAuth2 callback from TrueLayer.
    Extracts tenant_id from state, exchanges code for tokens, stores encrypted credentials,
    sets status to 'syncing', and enqueues the initial sync job.
    All steps required — partial completion is a failure.
    """
    # Validate and extract tenant_id from state
    if ":" not in state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )
    tenant_id, _ = state.split(":", 1)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant_id in state",
        )

    # Exchange code for tokens
    try:
        token_data = await tl.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("TrueLayer token exchange failed for tenant %s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TrueLayer token exchange failed",
        )

    encrypted_credentials = token_data["encrypted_credentials"]

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": encrypted_credentials,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "truelayer",
                "encrypted_credentials": encrypted_credentials,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    # Enqueue initial sync
    try:
        await enqueue_truelayer_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue TrueLayer sync for integration %s (will retry later): %s",
            integration.id,
            type(exc).__name__,
        )

    return standard_response(
        data={"status": "syncing", "integration_id": integration.id}
    )


@router.get("/integrations/truelayer/status")
async def truelayer_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns TrueLayer connection status for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    # Fetch latest sync logs
    sync_logs = await db.integrationsynclog.find_many(
        where={"tenant_id": tenant_id, "integration_id": integration.id},
        order={"created_at": "desc"},
        take=5,
    )

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "recent_syncs": [
                {
                    "entity_type": log.entity_type,
                    "status": log.status,
                    "records_synced": log.records_synced,
                    "duration_ms": log.duration_ms,
                }
                for log in sync_logs
            ],
        }
    )


@router.post("/integrations/truelayer/sync")
async def trigger_truelayer_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually enqueues a TrueLayer sync job for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No TrueLayer integration found",
        )
    if integration.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TrueLayer integration is disconnected — reconnect first",
        )

    try:
        await enqueue_truelayer_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error(
            "Failed to enqueue TrueLayer sync for integration %s: %s",
            integration.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue sync job",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/truelayer/disconnect")
async def disconnect_truelayer(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the TrueLayer integration as disconnected and wipes stored credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No TrueLayer integration found",
        )
    if integration.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TrueLayer integration is already disconnected",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
