"""Stripe Connect OAuth routes — connect, callback, status, sync, disconnect."""
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
from app.core.security import RequireOrgAuth, CurrentUser
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.stripe import client as stripe_client
from app.integrations.stripe.sync import enqueue_stripe_sync

logger = get_logger(__name__)
router = APIRouter(tags=["stripe"])


@router.get("/integrations/stripe/connect")
async def stripe_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the Stripe Connect OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = stripe_client.build_stripe_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/stripe/callback")
async def stripe_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Stripe Connect. Exchanges code for access_token,
    encrypts and stores credentials, sets status=syncing, enqueues sync job.
    Redirects to /dashboard/integrations?connected=stripe on success.
    All steps required — partial completion is a failure.
    """
    # Validate and extract tenant_id from state (format: "{tenant_id}:{random}")
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter",
        )
    tenant_id = parts[0]

    # Verify tenant exists
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Exchange OAuth code for access_token + stripe_user_id
    try:
        tokens = await stripe_client.exchange_stripe_code(code=code)
    except Exception as exc:
        logger.error("Stripe OAuth code exchange failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe token exchange failed",
        )

    # Encrypt credentials with tenant-specific key — never log token values
    encrypted = encrypt_credentials(tokens, tenant_id)

    # Upsert integration record — status=syncing until sync job confirms data present
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "stripe"}
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
                "type": "stripe",
                "encrypted_credentials": encrypted,
                "status": "syncing",
                "connected_at": datetime.now(UTC),
            }
        )

    # Enqueue sync job — confirms connection and fetches initial data
    try:
        await enqueue_stripe_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "Failed to enqueue Stripe sync after connect (will retry later): %s",
            type(exc).__name__,
        )

    frontend_url = get_settings().frontend_url.rstrip("/")
    return connected_page("Stripe", f"{frontend_url}/dashboard/integrations?connected=stripe")


@router.get("/integrations/stripe/status")
async def stripe_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Stripe integration status and connected_at for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "stripe"}
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


@router.post("/integrations/stripe/sync")
async def stripe_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually triggers a Stripe sync job for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "stripe"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Stripe integration found",
        )

    await db.integration.update(where={"id": integration.id}, data={"status": "syncing"})

    try:
        await enqueue_stripe_sync(
            integration_id=integration.id,
            tenant_id=current_user.tenant_id,
        )
    except Exception as exc:
        logger.error("Failed to enqueue Stripe sync: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync job",
        )

    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/stripe/disconnect")
async def stripe_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Deauthorizes Stripe Connect and marks the integration as disconnected."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "stripe", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Stripe integration found",
        )

    # Deauthorize at Stripe — best effort; proceed with local disconnect regardless
    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        stripe_user_id = creds.get("stripe_user_id", "")
        if stripe_user_id:
            await stripe_client.deauthorize_stripe(stripe_user_id)
    except Exception as exc:
        logger.warning(
            "Stripe deauthorization failed (proceeding with local disconnect): %s",
            type(exc).__name__,
        )

    # Wipe credentials and mark disconnected
    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
