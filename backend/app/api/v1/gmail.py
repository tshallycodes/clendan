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
    settings = get_settings()
    logger.info("gmail_connect_start", extra={
        "tenant_id": current_user.tenant_id,
        "client_id": (settings.google_client_id[:12] + "...") if settings.google_client_id else "MISSING",
        "redirect_uri": settings.google_redirect_uri_gmail,
        "has_client_secret": bool(settings.google_client_secret),
    })
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = google.build_gmail_auth_url(state=state)
    logger.info("gmail_connect_url_built", extra={"tenant_id": current_user.tenant_id, "url_prefix": auth_url[:80]})
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Handles Google OAuth callback for Gmail.
    Exchanges code, sets up Gmail watch, stores encrypted credentials, enqueues sync.
    All steps required - partial completion is a failure.
    """
    # Parse and validate state: "{tenant_id}:{random}"
    parts = state.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    tenant_id = parts[0]
    logger.info("gmail_callback_received", extra={"tenant_id": tenant_id, "has_code": bool(code), "state_valid": True})

    # Verify tenant exists
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        logger.error("gmail_callback_tenant_not_found", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found")
    logger.info("gmail_callback_tenant_ok", extra={"tenant_id": tenant_id})

    # Exchange authorization code for tokens
    settings = get_settings()
    logger.info("gmail_callback_exchange_start", extra={
        "tenant_id": tenant_id,
        "redirect_uri": settings.google_redirect_uri_gmail,
        "client_id": (settings.google_client_id[:12] + "...") if settings.google_client_id else "MISSING",
        "has_secret": bool(settings.google_client_secret),
    })
    try:
        encrypted_creds_str = await google.exchange_code(
            code=code,
            redirect_uri=settings.google_redirect_uri_gmail,
            tenant_id=tenant_id,
        )
        logger.info("gmail_callback_exchange_ok", extra={"tenant_id": tenant_id})
    except Exception as exc:
        logger.error("gmail_token_exchange_failed", extra={"tenant_id": tenant_id, "error": str(exc), "error_type": type(exc).__name__})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gmail token exchange failed: {type(exc).__name__}: {exc}")

    # Decrypt to read tokens for watch setup
    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
        logger.info("gmail_callback_decrypt_ok", extra={"tenant_id": tenant_id, "has_access_token": bool(creds.get("access_token")), "has_refresh_token": bool(creds.get("refresh_token"))})
    except ValueError as exc:
        logger.error("gmail_callback_decrypt_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential processing failed")

    access_token = creds.get("access_token", "")

    # Set up Gmail watch
    watch_result: dict = {}
    if settings.google_pubsub_topic:
        logger.info("gmail_callback_watch_setup_start", extra={"tenant_id": tenant_id, "topic": settings.google_pubsub_topic})
        try:
            watch_result = await google.setup_gmail_watch(access_token, settings.google_pubsub_topic)
            creds["history_id"] = watch_result.get("historyId", "")
            creds["watch_expiry"] = watch_result.get("expiration", "")
            logger.info("gmail_callback_watch_setup_ok", extra={"tenant_id": tenant_id, "history_id": watch_result.get("historyId")})
        except Exception as exc:
            logger.warning("gmail_watch_setup_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
    else:
        logger.info("gmail_callback_watch_skipped_no_topic", extra={"tenant_id": tenant_id})

    # Re-encrypt with watch metadata included
    final_encrypted = encrypt_credentials(creds, tenant_id)

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    try:
        if existing:
            integration = await db.integration.update(
                where={"id": existing.id},
                data={"encrypted_credentials": final_encrypted, "status": "syncing", "connected_at": datetime.now(UTC)},
            )
            logger.info("gmail_callback_integration_updated", extra={"tenant_id": tenant_id, "integration_id": existing.id})
        else:
            integration = await db.integration.create(
                data={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "encrypted_credentials": final_encrypted, "status": "syncing", "connected_at": datetime.now(UTC)},
            )
            logger.info("gmail_callback_integration_created", extra={"tenant_id": tenant_id, "integration_id": integration.id})
    except Exception as exc:
        logger.error("gmail_callback_db_write_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
        raise

    # Enqueue background sync
    try:
        await enqueue_gmail_sync(integration_id=integration.id, tenant_id=tenant_id)
        logger.info("gmail_callback_sync_enqueued", extra={"tenant_id": tenant_id, "integration_id": integration.id})
    except Exception as exc:
        logger.warning("gmail_sync_enqueue_failed", extra={"tenant_id": tenant_id, "error": str(exc)})

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
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "summary": integration.sync_metadata,
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
            detail=f"Cannot trigger sync - current status: {integration.status}",
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
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
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
        logger.warning("gmail_disconnect_decrypt_failed tenant=%s - proceeding with disconnect", tenant_id)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
