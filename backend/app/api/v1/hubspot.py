"""
HubSpot OAuth integration routes.
Handles connect, callback, status, manual sync trigger, and disconnect.
No webhooks — HubSpot integration uses polling-based sync.
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.config import get_settings
from app.core.oauth_html import connected_page
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials
from app.integrations.hubspot import client as hs
from app.integrations.hubspot.sync import enqueue_hubspot_sync

logger = get_logger(__name__)
router = APIRouter(tags=["hubspot"])


@router.get("/integrations/hubspot/connect")
async def hubspot_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the HubSpot OAuth authorization URL. Frontend redirects user here."""
    settings = get_settings()
    logger.info("hubspot_connect_start", extra={
        "tenant_id": current_user.tenant_id,
        "client_id": (settings.hubspot_client_id[:12] + "...") if settings.hubspot_client_id else "MISSING",
        "redirect_uri": settings.hubspot_redirect_uri,
        "has_client_secret": bool(settings.hubspot_client_secret),
    })
    # OAuth 2.1 PKCE: generate verifier+challenge, embed verifier in state so the
    # callback can retrieve it without external storage.
    # State format: {tenant_id}:{nonce}:{code_verifier}
    nonce = secrets.token_urlsafe(16)
    code_verifier, code_challenge = hs.generate_pkce_pair()
    state = f"{current_user.tenant_id}:{nonce}:{code_verifier}"
    auth_url = hs.build_auth_url(state=state, code_challenge=code_challenge)
    logger.info("hubspot_connect_url_built", extra={
        "tenant_id": current_user.tenant_id,
        "url_prefix": auth_url[:80],
        "pkce": "S256",
    })
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/hubspot/callback")
async def hubspot_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from HubSpot. Exchanges code for tokens, fetches portal info,
    stores encrypted credentials, enqueues initial sync.
    Redirects to /dashboard/integrations?connected=hubspot on success.
    All steps required — partial completion is a failure.
    """
    # State format: {tenant_id}:{nonce}:{code_verifier}
    # Use maxsplit=2 so the verifier (which may contain base64url chars) is preserved intact.
    parts = state.split(":", 2)
    if len(parts) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    tenant_id = parts[0]
    code_verifier = parts[2] if len(parts) == 3 else ""
    logger.info("hubspot_callback_received", extra={
        "tenant_id": tenant_id,
        "has_code": bool(code),
        "has_verifier": bool(code_verifier),
        "state_parts": len(parts),
    })

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        logger.error("hubspot_callback_tenant_not_found", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    logger.info("hubspot_callback_tenant_ok", extra={"tenant_id": tenant_id})

    settings = get_settings()
    try:
        encrypted_blob = await hs.exchange_code(code=code, tenant_id=tenant_id, code_verifier=code_verifier)
        logger.info("hubspot_callback_exchange_ok", extra={"tenant_id": tenant_id})
    except Exception as exc:
        logger.error("hubspot_token_exchange_failed", extra={"tenant_id": tenant_id, "error": str(exc), "error_type": type(exc).__name__})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"HubSpot token exchange failed: {type(exc).__name__}: {exc}",
        )

    try:
        raw_creds = decrypt_credentials(encrypted_blob, tenant_id)
        access_token = raw_creds["access_token"]
        logger.info("hubspot_callback_decrypt_ok", extra={"tenant_id": tenant_id, "has_access_token": bool(access_token), "has_refresh_token": bool(raw_creds.get("refresh_token"))})
    except Exception as exc:
        logger.error("hubspot_creds_decrypt_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential processing failed")

    logger.info("hubspot_callback_portal_info_start", extra={"tenant_id": tenant_id})
    try:
        portal_info = await hs.get_portal_info(access_token=access_token)
        portal_id = str(portal_info.get("hub_id", ""))
        logger.info("hubspot_callback_portal_info_ok", extra={"tenant_id": tenant_id, "portal_id": portal_id})
    except Exception as exc:
        logger.error("hubspot_portal_info_failed", extra={"tenant_id": tenant_id, "error": str(exc), "error_type": type(exc).__name__})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch HubSpot portal info: {type(exc).__name__}: {exc}",
        )

    # Re-encrypt with portal_id merged in
    from app.integrations.encryption import encrypt_credentials
    final_creds = {
        "access_token": raw_creds["access_token"],
        "refresh_token": raw_creds["refresh_token"],
        "portal_id": portal_id,
        "token_expiry_at": raw_creds["token_expiry_at"],
    }
    credentials_blob = encrypt_credentials(final_creds, tenant_id)

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "hubspot"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": credentials_blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "hubspot",
                "encrypted_credentials": credentials_blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    logger.info(
        "hubspot_connected tenant=%s portal_id=%s integration=%s",
        tenant_id,
        portal_id,
        integration.id,
    )

    # Enqueue initial sync — non-fatal if queue is temporarily unavailable
    try:
        await enqueue_hubspot_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "hubspot_sync_enqueue_failed integration=%s error=%s (will retry later)",
            integration.id,
            type(exc).__name__,
        )

    frontend_url = get_settings().frontend_url.rstrip("/")
    return connected_page("HubSpot", f"{frontend_url}/dashboard/integrations?connected=hubspot")


@router.get("/integrations/hubspot/status")
async def hubspot_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current HubSpot connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": (
                integration.connected_at.isoformat()
                if integration.connected_at
                else None
            ),
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/hubspot/sync")
async def hubspot_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a HubSpot sync job for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HubSpot connection found",
        )

    if integration.status not in ("connected", "syncing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot sync — integration status is '{integration.status}'",
        )

    try:
        await enqueue_hubspot_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error(
            "hubspot_manual_sync_enqueue_failed integration=%s error=%s",
            integration.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync — queue may be temporarily unavailable",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/hubspot/disconnect")
async def hubspot_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Wipes HubSpot credentials and marks integration as disconnected."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "hubspot", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No HubSpot connection found",
        )

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    logger.info(
        "hubspot_disconnected tenant=%s integration=%s",
        current_user.tenant_id,
        integration.id,
    )

    return standard_response(data={"status": "disconnected"})
