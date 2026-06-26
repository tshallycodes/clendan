"""
FreshBooks OAuth integration routes.
Flow: connect → callback → sync → status / disconnect
"""
import secrets
import urllib.parse
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.freshbooks import client as fb
from app.integrations.freshbooks.sync import sync_freshbooks_connection

logger = get_logger(__name__)
router = APIRouter(tags=["freshbooks"])

_AUTH_URL = "https://auth.freshbooks.com/oauth/authorize"
_SCOPE = (
    "user:profile:read user:bills:read user:bills:write "
    "user:invoices:read user:invoices:write user:payments:read "
    "user:clients:read user:expenses:read user:expenses:write "
    "user:staff:read"
)


@router.get("/integrations/freshbooks/connect")
async def freshbooks_connect(current_user: RequireOrgAuth):
    """Returns the FreshBooks OAuth authorization URL. Frontend redirects the user there."""
    settings = get_settings()
    if not settings.freshbooks_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FreshBooks OAuth credentials are not configured on this server",
        )

    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    params = {
        "client_id": settings.freshbooks_client_id,
        "response_type": "code",
        "redirect_uri": settings.freshbooks_redirect_uri,
        "scope": _SCOPE,
        "state": state,
    }
    auth_url = _AUTH_URL + "?" + urllib.parse.urlencode(params)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/freshbooks/callback")
async def freshbooks_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from FreshBooks.
    1. Validates state, extracts tenant_id.
    2. Exchanges code for tokens.
    3. Fetches user profile to resolve account_id.
    4. Stores encrypted credentials, enqueues sync.
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    try:
        tokens = await fb.exchange_code(code)
    except Exception as exc:
        logger.error("freshbooks_token_exchange_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="FreshBooks token exchange failed")

    # Resolve account_id and user_id eagerly — needed for all subsequent API calls
    try:
        me = await fb.get_me(tokens["access_token"])
        account_id = fb.extract_account_id(me)
    except Exception as exc:
        logger.error("freshbooks_get_me_failed tenant=%s: %s", tenant_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Connected to FreshBooks but failed to retrieve account details",
        )

    # Extract staff ID candidates from the me response.
    # The account-scoped staffid is NOT the global user id — it comes from the business membership.
    memberships = me.get("business_memberships", [])
    freshbooks_user_id = me.get("id")
    freshbooks_membership_id = memberships[0].get("id") if memberships else None
    freshbooks_business_id = memberships[0].get("business", {}).get("id") if memberships else None

    creds = {
        **tokens,
        "account_id": account_id,
        "freshbooks_user_id": freshbooks_user_id,
        "freshbooks_membership_id": freshbooks_membership_id,
        "freshbooks_business_id": freshbooks_business_id,
    }
    blob = encrypt_credentials(creds, tenant_id)

    existing = await db.integration.find_first(where={"tenant_id": tenant_id, "type": "freshbooks"})
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={"encrypted_credentials": blob, "status": "syncing", "connected_at": datetime.now(UTC)},
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "freshbooks",
                "encrypted_credentials": blob,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    background_tasks.add_task(sync_freshbooks_connection, {}, integration.id, tenant_id)

    frontend_url = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(url=f"{frontend_url}/dashboard/integrations?connected=freshbooks")


@router.get("/integrations/freshbooks/status")
async def freshbooks_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current FreshBooks connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "freshbooks"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(data={
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "integration_id": integration.id,
        "summary": integration.sync_metadata,
    })


@router.post("/integrations/freshbooks/sync")
async def freshbooks_sync(
    background_tasks: BackgroundTasks,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a background FreshBooks sync for the authenticated tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "freshbooks", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active FreshBooks connection found")

    background_tasks.add_task(sync_freshbooks_connection, {}, integration.id, tenant_id)
    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/freshbooks/disconnect")
async def freshbooks_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes FreshBooks token and marks integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "freshbooks", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No FreshBooks connection found")

    # Best-effort token revocation — FreshBooks doesn't have a dedicated revoke endpoint
    # so we simply wipe credentials from our side
    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        logger.info(
            "freshbooks_disconnected tenant=%s account_id=%s",
            tenant_id, creds.get("account_id", "unknown"),
        )
    except Exception:
        pass

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
