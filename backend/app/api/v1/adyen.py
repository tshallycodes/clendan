"""
Adyen integration routes.
API key auth — no OAuth flow required.
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
from app.integrations.adyen import client as adyen_client
from app.integrations.adyen.sync import enqueue_adyen_sync

logger = get_logger(__name__)
router = APIRouter(tags=["adyen"])

INTEGRATION_TYPE = "adyen"


class AdyenConnectRequest(BaseModel):
    api_key: str
    merchant_account: str
    environment: str = "live"

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in ("test", "live"):
            raise ValueError("environment must be 'test' or 'live'")
        return v


@router.post("/integrations/adyen/connect")
async def connect_adyen(
    body: AdyenConnectRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Connects an Adyen account using an API key and merchant account.
    Validates the key before storing. Stores encrypted credentials then enqueues initial sync.
    """
    tenant_id = current_user.tenant_id

    # Validate API key before storing anything
    try:
        await adyen_client.validate_connection(
            body.api_key, body.merchant_account, body.environment
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Adyen API key validation failed: tenant=%s status=%d",
            tenant_id,
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adyen API key is invalid or does not have the required permissions",
        )
    except ValueError as exc:
        logger.warning(
            "Adyen connection validation returned empty response: tenant=%s", tenant_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adyen merchant account not found or API key lacks access",
        )
    except Exception as exc:
        logger.error("Adyen API key validation error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Adyen to validate API key",
        )

    encrypted = encrypt_credentials(
        {
            "api_key": body.api_key,
            "merchant_account": body.merchant_account,
            "environment": body.environment,
        },
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
        await enqueue_adyen_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue Adyen sync (will retry later): %s", type(exc).__name__
        )

    logger.info(
        "Adyen connected: tenant=%s merchant_account=%s environment=%s",
        tenant_id,
        body.merchant_account,
        body.environment,
    )

    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "merchant_account": body.merchant_account,
            "environment": body.environment,
        }
    )


@router.get("/integrations/adyen/status")
async def adyen_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Adyen connection status and connected_at timestamp for the tenant. Never exposes api_key."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    # Decrypt only to surface safe fields — never expose the api_key
    environment = None
    merchant_account = None
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
            environment = creds.get("environment")
            merchant_account = creds.get("merchant_account")
        except ValueError:
            logger.warning(
                "Adyen credential decryption failed for status check: tenant=%s", tenant_id
            )

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "environment": environment,
            "merchant_account": merchant_account,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/adyen/sync")
async def trigger_adyen_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually enqueues an Adyen sync job for the tenant's active integration."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Adyen connection found",
        )

    try:
        await enqueue_adyen_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("Adyen sync enqueue failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to enqueue Adyen sync",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/adyen/disconnect")
async def disconnect_adyen(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the Adyen integration as disconnected and wipes stored credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Adyen connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("Adyen disconnected: tenant=%s", tenant_id)

    return standard_response(data={"status": "disconnected"})
