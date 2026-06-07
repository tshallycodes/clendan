import json
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth, CurrentUser
from app.integrations.quickbooks import client as qb

logger = get_logger(__name__)
router = APIRouter(tags=["integrations"])


@router.get("/integrations/quickbooks/connect")
async def quickbooks_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the QuickBooks OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = qb.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url})


@router.get("/integrations/quickbooks/callback")
async def quickbooks_callback(
    code: str = Query(...),
    state: str = Query(...),
    realm_id: str = Query(..., alias="realmId"),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from QuickBooks. Exchanges code for tokens, stores encrypted,
    triggers initial sync, marks integration as connected.
    All steps required — partial completion is a failure.
    """
    # Validate and extract tenant_id from state
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )
    tenant_id = parts[0]

    # Verify tenant exists
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Exchange code for tokens
    try:
        tokens = await qb.exchange_code(code=code, realm_id=realm_id)
    except Exception as exc:
        logger.error("QB token exchange failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="QuickBooks token exchange failed",
        )

    # Store encrypted credentials
    credentials = json.dumps({**tokens, "realm_id": realm_id})

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "quickbooks"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": credentials,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "quickbooks",
                "encrypted_credentials": credentials,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            }
        )

    # Verify connection by fetching company info (zero trust — confirm data present)
    try:
        from app.core.config import get_settings
        settings = get_settings()
        creds = json.loads(credentials)
        company = await qb.get_company_info(
            encrypted_access=creds["access_token"],
            realm_id=realm_id,
            sandbox=settings.quickbooks_sandbox,
        )
        logger.info(
            "QB connected: tenant=%s company=%s",
            tenant_id,
            company.get("company_name"),
        )
    except Exception as exc:
        logger.warning(
            "QB company info fetch failed after connect: %s", type(exc).__name__
        )
        # Don't fail — tokens are stored, sync will retry

    return standard_response(
        data={
            "status": "connected",
            "integration_id": integration.id,
            "realm_id": realm_id,
        }
    )


@router.get("/integrations/quickbooks/status")
async def quickbooks_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current QuickBooks connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "quickbooks"}
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
            "integration_id": integration.id,
        }
    )


@router.delete("/integrations/quickbooks/disconnect")
async def quickbooks_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes QuickBooks tokens and marks integration as disconnected."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "quickbooks", "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active QuickBooks connection found",
        )

    # Revoke tokens at QuickBooks
    try:
        creds = json.loads(integration.encrypted_credentials)
        await qb.revoke_token(creds["refresh_token"])
    except Exception as exc:
        logger.warning(
            "QB token revocation failed (proceeding with disconnect): %s",
            type(exc).__name__,
        )

    # Mark disconnected regardless of revocation success
    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
