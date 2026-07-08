"""
Google Drive integration routes.
OAuth flow: connect → callback → enqueue sync.
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from prisma import Prisma
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials
from app.integrations.google import client as google
from app.integrations.google.sync_drive import enqueue_drive_sync

logger = get_logger(__name__)
router = APIRouter(tags=["google-drive"])

INTEGRATION_TYPE = "google_drive"


class WatchFolderRequest(BaseModel):
    folder: str


@router.get("/integrations/google-drive/connect")
async def drive_connect(
    current_user: RequireOrgAuth,
):
    """Returns Google Drive OAuth authorization URL and state token."""
    settings = get_settings()
    logger.info("drive_connect_start", extra={
        "tenant_id": current_user.tenant_id,
        "client_id": (settings.google_client_id[:12] + "...") if settings.google_client_id else "MISSING",
        "redirect_uri": settings.google_redirect_uri_drive,
        "has_client_secret": bool(settings.google_client_secret),
    })
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = google.build_drive_auth_url(state=state)
    logger.info("drive_connect_url_built", extra={"tenant_id": current_user.tenant_id, "url_prefix": auth_url[:80]})
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/google-drive/callback")
async def drive_callback(
    code: str,
    state: str,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Handles Google OAuth callback for Drive.
    Exchanges code, stores encrypted credentials, enqueues sync.
    All steps required - partial completion is a failure.
    """
    # Parse and validate state: "{tenant_id}:{random}"
    parts = state.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    tenant_id = parts[0]
    logger.info("drive_callback_received", extra={"tenant_id": tenant_id, "has_code": bool(code)})

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        logger.error("drive_callback_tenant_not_found", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found")
    logger.info("drive_callback_tenant_ok", extra={"tenant_id": tenant_id})

    settings = get_settings()
    logger.info("drive_callback_exchange_start", extra={
        "tenant_id": tenant_id,
        "redirect_uri": settings.google_redirect_uri_drive,
        "client_id": (settings.google_client_id[:12] + "...") if settings.google_client_id else "MISSING",
        "has_secret": bool(settings.google_client_secret),
    })
    try:
        encrypted_creds_str = await google.exchange_code(
            code=code,
            redirect_uri=settings.google_redirect_uri_drive,
            tenant_id=tenant_id,
        )
        logger.info("drive_callback_exchange_ok", extra={"tenant_id": tenant_id})
    except Exception as exc:
        logger.error("drive_token_exchange_failed", extra={"tenant_id": tenant_id, "error": str(exc), "error_type": type(exc).__name__})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Drive token exchange failed: {type(exc).__name__}: {exc}")

    existing = await db.integration.find_first(where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE})
    try:
        if existing:
            integration = await db.integration.update(
                where={"id": existing.id},
                data={"encrypted_credentials": encrypted_creds_str, "status": "syncing", "connected_at": datetime.now(UTC)},
            )
            logger.info("drive_callback_integration_updated", extra={"tenant_id": tenant_id, "integration_id": existing.id})
        else:
            integration = await db.integration.create(
                data={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "encrypted_credentials": encrypted_creds_str, "status": "syncing", "connected_at": datetime.now(UTC)},
            )
            logger.info("drive_callback_integration_created", extra={"tenant_id": tenant_id, "integration_id": integration.id})
    except Exception as exc:
        logger.error("drive_callback_db_write_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
        raise

    try:
        await enqueue_drive_sync(integration_id=integration.id, tenant_id=tenant_id)
        logger.info("drive_callback_sync_enqueued", extra={"tenant_id": tenant_id, "integration_id": integration.id})
    except Exception as exc:
        logger.warning("drive_sync_enqueue_failed", extra={"tenant_id": tenant_id, "error": str(exc)})

    frontend_url = settings.frontend_url
    return RedirectResponse(url=f"{frontend_url}/dashboard/integrations?connected=google_drive")


@router.get("/integrations/google-drive/status")
async def drive_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Google Drive integration status for the tenant."""
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
            "watch_folder": integration.watch_folder,
        }
    )


@router.patch("/integrations/google-drive/watch-folder")
async def drive_set_watch_folder(
    body: WatchFolderRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Set the Drive folder to watch. Only PDFs inside it are processed. Saving a non-empty
    folder triggers a sync so existing files are backfilled immediately."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Google Drive integration found")

    folder = body.folder.strip() or None
    await db.integration.update(
        where={"id": integration.id},
        data={"watch_folder": folder, "status": "syncing" if folder else integration.status},
    )

    if folder:
        try:
            await enqueue_drive_sync(integration_id=integration.id, tenant_id=tenant_id)
        except Exception as exc:
            logger.error("drive_watch_folder_sync_enqueue_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    return standard_response(data={"watch_folder": folder, "integration_id": integration.id})


@router.post("/integrations/google-drive/sync")
async def drive_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Google Drive sync for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Google Drive integration found")

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
        await enqueue_drive_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("drive_manual_sync_enqueue_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to enqueue Drive sync")

    return standard_response(data={"status": "syncing", "integration_id": integration.id})


@router.delete("/integrations/google-drive/disconnect")
async def drive_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes token and marks Google Drive integration as disconnected."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": INTEGRATION_TYPE, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Google Drive integration found")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        refresh_token = creds.get("refresh_token", "")
        access_token = creds.get("access_token", "")

        if refresh_token or access_token:
            try:
                token_to_revoke = refresh_token or access_token
                await google.revoke_google_token(token_to_revoke)
            except Exception as exc:
                logger.warning("drive_revoke_token_failed tenant=%s: %s", tenant_id, type(exc).__name__)

    except ValueError:
        logger.warning("drive_disconnect_decrypt_failed tenant=%s - proceeding with disconnect", tenant_id)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
