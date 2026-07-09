"""
Microsoft Outlook (Graph API) integration routes.
Handles OAuth connect flow, status, manual sync trigger, and disconnect.
"""
import json
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.outlook import client as outlook
from app.integrations.outlook.sync import enqueue_outlook_sync

logger = get_logger(__name__)
router = APIRouter(tags=["outlook"])


class EmailFilterRequest(BaseModel):
    folder: str


@router.get("/integrations/outlook/connect")
async def outlook_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Returns the Microsoft OAuth authorization URL.
    Frontend redirects user to this URL to begin the consent flow.
    state encodes tenant_id for extraction in the callback.
    """
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = outlook.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/outlook/callback")
async def outlook_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Microsoft identity platform.
    Exchanges code for tokens, stores encrypted credentials, enqueues sync.
    state format: {tenant_id}:{random}
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

    # Exchange code for tokens
    try:
        encrypted_creds_str = await outlook.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("outlook_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Microsoft token exchange failed",
        )

    # Fetch user email to store alongside credentials
    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
        user_info = await outlook.get_user_info(creds["access_token"])
        email = user_info.get("email", "")
        creds["email"] = email
        encrypted_creds_str = encrypt_credentials(creds, tenant_id)
    except Exception as exc:
        logger.warning(
            "outlook_user_info_fetch_failed tenant=%s: %s", tenant_id, type(exc).__name__
        )
        email = ""

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "outlook"}
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
                "type": "outlook",
                "encrypted_credentials": encrypted_creds_str,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    # Enqueue initial sync (creates subscription + scans messages)
    try:
        await enqueue_outlook_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "outlook_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )

    logger.info(
        "outlook_callback_ok tenant=%s integration_id=%s email=%s",
        tenant_id, integration.id, email,
    )
    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "email": email,
        }
    )


@router.get("/integrations/outlook/status")
async def outlook_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the current Outlook integration status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "outlook"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    email = ""
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            email = creds.get("email", "")
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
            "email": email,
            "summary": integration.sync_metadata,
            "watch_folder": integration.watch_folder,
        }
    )


@router.patch("/integrations/outlook/watch-folder")
async def outlook_set_filter(
    body: EmailFilterRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Set the Outlook OData filter that scopes which emails are ingested (e.g.
    contains(subject,'invoice')). Empty = process nothing. Saving a non-empty filter
    triggers a sync so matching emails are picked up immediately."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "outlook", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Outlook integration found")

    folder = body.folder.strip() or None
    await db.integration.update(
        where={"id": integration.id},
        data={"watch_folder": folder, "status": "syncing" if folder else integration.status},
    )
    if folder:
        try:
            await enqueue_outlook_sync(integration_id=integration.id, tenant_id=current_user.tenant_id)
        except Exception as exc:
            logger.error("outlook_filter_sync_enqueue_failed tenant=%s: %s", current_user.tenant_id, type(exc).__name__)

    return standard_response(data={"watch_folder": folder, "integration_id": integration.id})


@router.post("/integrations/outlook/sync")
async def outlook_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers an Outlook sync for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "outlook"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Outlook integration found",
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
        await enqueue_outlook_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error(
            "outlook_manual_sync_enqueue_failed integration_id=%s: %s",
            integration.id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync - queue may be unavailable",
        )

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.delete("/integrations/outlook/disconnect")
async def outlook_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Deletes the Graph API subscription, wipes credentials,
    and marks the integration as disconnected.
    """
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "outlook", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Outlook connection found",
        )

    # Delete Graph subscription before wiping credentials
    if integration.encrypted_credentials and integration.encrypted_credentials != "{}":
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
            subscription_id = creds.get("subscription_id", "")
            access_token = creds.get("access_token", "")
            if subscription_id and access_token:
                await outlook.delete_subscription(
                    access_token=access_token,
                    subscription_id=subscription_id,
                )
        except Exception as exc:
            logger.warning(
                "outlook_subscription_delete_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}", "watch_folder": None},
    )

    logger.info(
        "outlook_disconnected tenant=%s integration_id=%s",
        current_user.tenant_id, integration.id,
    )
    return standard_response(data={"status": "disconnected"})
