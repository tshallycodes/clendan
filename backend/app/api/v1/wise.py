"""
Wise integration routes.
API token auth - no OAuth flow required.
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
from app.integrations.wise import client as wise_client
from app.integrations.wise.sync import enqueue_wise_sync

logger = get_logger(__name__)
router = APIRouter(tags=["wise"])

INTEGRATION_TYPE = "wise"


class WiseConnectRequest(BaseModel):
    api_token: str
    environment: str = "live"

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("sandbox", "live"):
            raise ValueError("environment must be 'sandbox' or 'live'")
        return v


@router.post("/integrations/wise/connect")
async def connect_wise(
    body: WiseConnectRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Connects a Wise account using an API token.
    Validates the token against /v1/profiles before storing.
    Stores encrypted credentials then enqueues initial sync.
    """
    tenant_id = current_user.tenant_id

    # Validate API token before storing anything
    try:
        profiles = await wise_client.validate_api_token(body.api_token, body.environment)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Wise API token validation failed: tenant=%s status=%d",
            tenant_id,
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wise API token is invalid or does not have the required permissions",
        )
    except ValueError as exc:
        logger.warning("Wise API token validation rejected: tenant=%s reason=%s", tenant_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Wise API token validation error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Wise to validate API token",
        )

    encrypted = encrypt_credentials(
        {"api_token": body.api_token, "environment": body.environment},
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
        await enqueue_wise_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue Wise sync (will retry later): %s", type(exc).__name__
        )

    logger.info(
        "Wise connected: tenant=%s environment=%s profiles_found=%d",
        tenant_id,
        body.environment,
        len(profiles),
    )

    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "environment": body.environment,
            "profiles_found": len(profiles),
        }
    )


@router.get("/integrations/wise/status")
async def wise_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Wise connection status and connected_at timestamp for the tenant. Never returns the API token."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    # Decrypt only to expose environment - never expose the api_token
    environment = None
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
            environment = creds.get("environment")
        except ValueError:
            logger.warning(
                "Wise credential decryption failed for status check: tenant=%s", tenant_id
            )

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "environment": environment,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/wise/sync")
async def trigger_wise_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually enqueues a Wise sync job for the tenant's active integration."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Wise connection found",
        )

    try:
        await enqueue_wise_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("Wise sync enqueue failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue Wise sync",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/wise/disconnect")
async def disconnect_wise(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the Wise integration as disconnected and wipes stored credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Wise connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("Wise disconnected: tenant=%s", tenant_id)

    return standard_response(data={"status": "disconnected"})
