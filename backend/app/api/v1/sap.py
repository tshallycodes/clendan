"""
SAP S/4HANA Cloud integration routes.
Uses OAuth 2.0 Client Credentials — no OAuth redirect flow.
Credentials are supplied directly by the tenant at connect time.
"""
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.sap import client as sap
from app.integrations.sap.sync import enqueue_sap_sync

logger = get_logger(__name__)
router = APIRouter(tags=["sap"])

INTEGRATION_TYPE = "sap"


class SapConnectRequest(BaseModel):
    client_id: str
    client_secret: str
    token_url: str
    api_base_url: str


@router.post("/integrations/sap/connect")
async def sap_connect(
    body: SapConnectRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Connects a SAP S/4HANA Cloud account using OAuth 2.0 client credentials.
    Validates credentials by fetching a token before storing anything.
    Stores encrypted credentials and enqueues initial sync.
    """
    tenant_id = current_user.tenant_id

    if not all([body.client_id, body.client_secret, body.token_url, body.api_base_url]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_id, client_secret, token_url, and api_base_url are all required",
        )

    try:
        await sap.get_access_token(body.client_id, body.client_secret, body.token_url)
    except Exception as exc:
        logger.error(
            "sap_connect_token_validation_failed tenant=%s error=%s",
            tenant_id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not obtain an access token from SAP — verify client_id, client_secret, and token_url",
        )

    raw_creds = {
        "client_id": body.client_id,
        "client_secret": body.client_secret,
        "token_url": body.token_url,
        "api_base_url": body.api_base_url,
    }
    encrypted = encrypt_credentials(raw_creds, tenant_id)

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
        await enqueue_sap_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "sap_sync_enqueue_failed integration_id=%s error=%s (will retry later)",
            integration.id, type(exc).__name__,
        )

    logger.info("sap_connected tenant=%s integration_id=%s", tenant_id, integration.id)
    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.get("/integrations/sap/status")
async def sap_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns SAP connection status for the authenticated tenant. Never exposes client_secret."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    token_url = None
    api_base_url = None
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
            token_url = creds.get("token_url")
            api_base_url = creds.get("api_base_url")
        except ValueError:
            logger.warning(
                "sap_status_decrypt_failed tenant=%s integration_id=%s",
                tenant_id, integration.id,
            )

    return standard_response(data={
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "integration_id": integration.id,
        "token_url": token_url,
        "api_base_url": api_base_url,
        "summary": integration.sync_metadata,
    })


@router.post("/integrations/sap/sync")
async def sap_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually enqueues a SAP sync job for the authenticated tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active SAP connection found",
        )

    try:
        await enqueue_sap_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error(
            "sap_manual_sync_enqueue_failed integration_id=%s error=%s",
            integration.id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync — queue may be temporarily unavailable",
        )

    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/sap/disconnect")
async def sap_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Wipes SAP credentials and marks the integration as disconnected."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SAP connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info("sap_disconnected tenant=%s integration_id=%s", tenant_id, integration.id)
    return standard_response(data={"status": "disconnected"})
