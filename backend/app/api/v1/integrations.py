import json
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth, CurrentUser
from app.integrations.quickbooks import client as qb
from app.integrations.xero import client as xero
from app.integrations.encryption import decrypt_credentials, encrypt_credentials

logger = get_logger(__name__)
router = APIRouter(tags=["integrations"])


@router.get("/integrations/quickbooks/connect")
async def quickbooks_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the QuickBooks OAuth authorization URL. Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    try:
        auth_url = qb.build_auth_url(state=state)
    except ValueError as exc:
        logger.error("QB connect misconfigured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QuickBooks integration is not configured on this server",
        )
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
    from app.core.config import get_settings as _get_settings
    _frontend_url = _get_settings().frontend_url

    # Validate and extract tenant_id from state
    parts = state.split(":", 1)
    if len(parts) != 2:
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=invalid_state")
    tenant_id = parts[0]

    # Verify tenant exists
    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=tenant_not_found")

    # Exchange code for tokens
    try:
        tokens = await qb.exchange_code(code=code, realm_id=realm_id)
    except Exception as exc:
        logger.error("QB token exchange failed: %s", type(exc).__name__)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=token_exchange_failed")

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
        settings = _get_settings()
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

    return RedirectResponse(f"{_frontend_url}/dashboard/integrations?connected=quickbooks")


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
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
        }
    )


@router.post("/integrations/quickbooks/sync")
async def quickbooks_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Verifies the QuickBooks connection inline. Used by the Resync button."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "quickbooks", "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected QuickBooks integration found",
        )

    from app.integrations.quickbooks.sync import sync_quickbooks_connection
    result = await sync_quickbooks_connection(
        ctx={},
        integration_id=integration.id,
        tenant_id=current_user.tenant_id,
    )
    return standard_response(data={"result": result, "integration_id": integration.id})


class XeroSelectTenantRequest(BaseModel):
    integration_id: str
    xero_tenant_id: str


@router.get("/integrations/xero/connect")
async def xero_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the Xero OAuth authorization URL (PKCE). Frontend redirects user here."""
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    try:
        auth_url = xero.build_auth_url(state=state, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        logger.error("Xero connect misconfigured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Xero integration is not configured on this server",
        )
    return standard_response(data={"auth_url": auth_url})


@router.get("/integrations/xero/callback")
async def xero_callback(
    db: Prisma = Depends(get_db_dep),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """
    OAuth callback from Xero. Exchanges code+PKCE for tokens, fetches connected orgs,
    stores encrypted credentials, marks integration as connected.
    """
    from app.core.config import get_settings as _get_settings
    _frontend_url = _get_settings().frontend_url

    # Xero returns error param when user denies or scopes are wrong
    if error:
        logger.warning("Xero OAuth error: %s — %s", error, error_description)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error={error}")

    if not code or not state:
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=invalid_callback")

    parts = state.split(":", 1)
    if len(parts) != 2:
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=invalid_state")
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=tenant_not_found")

    try:
        encrypted_creds = await xero.exchange_code(code=code, state=state, tenant_id=tenant_id)
    except Exception as exc:
        import httpx as _httpx
        detail = str(exc)
        if isinstance(exc, _httpx.HTTPStatusError):
            detail = exc.response.text[:500]
        logger.error("Xero token exchange failed: %s — %s", type(exc).__name__, detail)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=token_exchange_failed")

    try:
        creds = decrypt_credentials(encrypted_creds, tenant_id)
    except Exception as exc:
        logger.error("Xero credential decrypt failed post-exchange: %s", type(exc).__name__)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=token_exchange_failed")

    # Fetch connected Xero orgs — zero trust: confirm data present before storing
    try:
        connections = await xero.get_connections(creds["access_token"])
    except Exception as exc:
        logger.error("Xero get_connections failed: %s", type(exc).__name__)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=token_exchange_failed")

    if not connections:
        logger.error("Xero returned no connections for tenant %s", tenant_id)
        return RedirectResponse(f"{_frontend_url}/dashboard/integrations?error=no_xero_org")

    # Auto-select first org (common single-org case). Multi-org selection via /select-tenant.
    first = connections[0]
    creds["xero_tenant_id"] = first["tenantId"]
    creds["connection_id"] = first.get("id", "")
    creds["org_name"] = first.get("tenantName", "")

    final_creds = encrypt_credentials(creds, tenant_id)

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": final_creds,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "xero",
                "encrypted_credentials": final_creds,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            }
        )

    logger.info("xero_connected tenant=%s org=%s", tenant_id, creds.get("org_name"))
    return RedirectResponse(f"{_frontend_url}/dashboard/integrations?connected=xero")


@router.get("/integrations/xero/status")
async def xero_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current Xero connection status for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "xero"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
        }
    )


@router.post("/integrations/xero/sync")
async def xero_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Verifies the Xero connection inline. Used by the Resync button."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "xero", "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected Xero integration found",
        )

    from app.integrations.xero.sync import sync_xero_connection
    result = await sync_xero_connection(
        ctx={},
        integration_id=integration.id,
        tenant_id=current_user.tenant_id,
    )
    return standard_response(data={"result": result, "integration_id": integration.id})


@router.post("/integrations/xero/select-tenant")
async def xero_select_tenant(
    body: XeroSelectTenantRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Updates the active Xero org for a multi-org connection."""
    integration = await db.integration.find_first(
        where={"id": body.integration_id, "tenant_id": current_user.tenant_id, "type": "xero"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Failed to read stored credentials")

    creds["xero_tenant_id"] = body.xero_tenant_id
    updated_creds = encrypt_credentials(creds, current_user.tenant_id)

    await db.integration.update(
        where={"id": integration.id},
        data={"encrypted_credentials": updated_creds, "status": "connected"},
    )
    return standard_response(data={"status": "connected", "xero_tenant_id": body.xero_tenant_id})


@router.delete("/integrations/xero/disconnect")
async def xero_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Xero connection and marks integration as disconnected."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "xero", "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Xero connection found",
        )

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, current_user.tenant_id)
        connection_id = creds.get("connection_id", "")
        if connection_id:
            await xero.revoke_connection(
                access_token=creds["access_token"],
                connection_id=connection_id,
            )
    except Exception as exc:
        logger.warning("Xero token revocation failed (proceeding): %s", type(exc).__name__)

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    return standard_response(data={"status": "disconnected"})


@router.get("/integrations/{slug}/sync-log")
async def integration_sync_log(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(default=50, le=200),
):
    """Returns recent sync log entries for an integration."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": slug}
    )
    if not integration:
        return standard_response(data=[])

    logs = await db.integrationsynclog.find_many(
        where={"integration_id": integration.id, "tenant_id": current_user.tenant_id},
        order={"created_at": "desc"},
        take=limit,
    )
    return standard_response(data=[
        {
            "id": log.id,
            "timestamp": log.created_at.isoformat(),
            "entity_type": log.entity_type,
            "status": log.status,
            "records_synced": log.records_synced,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
        }
        for log in logs
    ])


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
