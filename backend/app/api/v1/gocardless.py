"""
GoCardless integration routes.
API key auth - no OAuth flow required.
"""
from datetime import datetime, UTC
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.gocardless import client as gc
from app.integrations.gocardless.sync import enqueue_gocardless_sync

logger = get_logger(__name__)
router = APIRouter(tags=["gocardless"])

INTEGRATION_TYPE = "gocardless"


class GoCardlessConnectRequest(BaseModel):
    access_token: str
    environment: str = "live"

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("sandbox", "live"):
            raise ValueError("environment must be 'sandbox' or 'live'")
        return v


@router.post("/integrations/gocardless/connect")
async def connect_gocardless(
    body: GoCardlessConnectRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Connects a GoCardless account using an API key.
    Validates the key before storing. Stores encrypted credentials then enqueues initial sync.
    """
    tenant_id = current_user.tenant_id

    # Validate API key before storing anything
    try:
        creditor_info = await gc.validate_api_key(body.access_token, body.environment)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "GoCardless API key validation failed: tenant=%s status=%d",
            tenant_id,
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GoCardless API key is invalid or does not have the required permissions",
        )
    except Exception as exc:
        logger.error("GoCardless API key validation error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach GoCardless to validate API key",
        )

    encrypted = encrypt_credentials(
        {"access_token": body.access_token, "environment": body.environment},
        tenant_id,
    )

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
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
                "type": INTEGRATION_TYPE,
                "encrypted_credentials": encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    try:
        await enqueue_gocardless_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue GoCardless sync (will retry later): %s", type(exc).__name__
        )

    logger.info("GoCardless connected: tenant=%s environment=%s", tenant_id, body.environment)

    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "environment": body.environment,
            "creditors_found": len(creditor_info.get("creditors", [])),
        }
    )


@router.get("/integrations/gocardless/status")
async def gocardless_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns GoCardless connection status and connected_at timestamp for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    # Decrypt only to expose environment - never expose the token
    environment = None
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
            environment = creds.get("environment")
        except ValueError:
            logger.warning("GoCardless credential decryption failed for status check: tenant=%s", tenant_id)

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "environment": environment,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/gocardless/sync")
async def trigger_gocardless_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually enqueues a GoCardless sync job for the tenant's active integration."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active GoCardless connection found",
        )

    try:
        await enqueue_gocardless_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("GoCardless sync enqueue failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue GoCardless sync",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/gocardless/disconnect")
async def disconnect_gocardless(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the GoCardless integration as disconnected and wipes stored credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active GoCardless connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("GoCardless disconnected: tenant=%s", tenant_id)

    return standard_response(data={"status": "disconnected"})
