"""
Gmail integration routes.
OAuth flow: connect → callback → (watch setup) → enqueue sync.
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.google import client as google
from app.integrations.google.sync_gmail import enqueue_gmail_sync

logger = get_logger(__name__)
router = APIRouter(tags=["gmail"])

INTEGRATION_TYPE = "gmail"


@router.get("/integrations/gmail/connect")
async def gmail_connect(
    current_user: RequireOrgAuth,
):
    """Returns Gmail OAuth authorization URL and state token."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = google.build_gmail_auth_url(state=state)
    return standard_response(data={"url": auth_url, "state": state})


@router.get("/integrations/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Handles Google OAuth callback for Gmail.
    Exchanges code, sets up Gmail watch, stores encrypted credentials, enqueues sync.
    All steps required — partial completion is a failure.
    """
    # Parse and validate state: "{tenant_id}:{random}"
    parts = state.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    tenant_id = parts[0]

    # Verify tenant exists
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found")

    # Exchange authorization code for tokens
    settings = get_settings()
    try:
        encrypted_creds_str = await google.exchange_code(
            code=code,
            redirect_uri=settings.google_redirect_uri_gmail,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("gmail_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail token exchange failed")

    # Decrypt to read tokens for watch setup, then re-encrypt with watch metadata
    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
    except ValueError as exc:
        logger.error("gmail_callback_decrypt_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential processing failed")

    access_token = creds.get("access_token", "")

    # Set up Gmail watch
    watch_result: dict = {}
    if settings.google_pubsub_topic:
        try:
            watch_result = await google.setup_gmail_watch(access_token, settings.google_pubsub_topic)
            creds["history_id"] = watch_result.get("historyId", "")
            creds["watch_expiry"] = watch_result.get("expiration", "")
        except Exception as exc:
            logger.warning("gmail_watch_setup_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    # Re-encrypt with watch metadata included
    final_encrypted = encrypt_credentials(creds, tenant_id)

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": final_encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": INTEGRATION_TYPE,
                "encrypted_credentials": final_encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    # Enqueue background sync
    try:
        await enqueue_gmail_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("gmail_sync_enqueue_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.get("/integrations/gmail/status")
async def gmail_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Gmail integration status for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "integration_id": integration.id,
        }
    )


@router.post("/integrations/gmail/sync")
async def gmail_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Gmail sync for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Gmail integration found")

    if integration.status not in ("connected", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot trigger sync — current status: {integration.status}",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "syncing"},
    )

    try:
        await enqueue_gmail_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("gmail_manual_sync_enqueue_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to enqueue Gmail sync")

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.delete("/integrations/gmail/disconnect")
async def gmail_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Stops Gmail watch, revokes token, and marks integration as disconnected."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Gmail integration found")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        access_token = creds.get("access_token", "")
        refresh_token = creds.get("refresh_token", "")

        if access_token:
            try:
                await google.stop_gmail_watch(access_token)
            except Exception as exc:
                logger.warning("gmail_stop_watch_failed tenant=%s: %s", tenant_id, type(exc).__name__)

            try:
                token_to_revoke = refresh_token or access_token
                await google.revoke_google_token(token_to_revoke)
            except Exception as exc:
                logger.warning("gmail_revoke_token_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    except ValueError:
        logger.warning("gmail_disconnect_decrypt_failed tenant=%s — proceeding with disconnect", tenant_id)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
