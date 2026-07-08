"""
Xero OAuth integration routes.
Flow: connect → callback (multi-org check) → [select-tenant] → sync → status / disconnect
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from pydantic import BaseModel
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.xero import client as xero
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)
router = APIRouter(tags=["xero"])


class SelectTenantRequest(BaseModel):
    integration_id: str
    xero_tenant_id: str


@router.get("/integrations/xero/connect")
async def xero_connect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Returns the Xero OAuth authorization URL.
    Generates a PKCE verifier+challenge and stores verifier keyed by state.
    Frontend redirects the user to auth_url.
    """
    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    auth_url = xero.build_auth_url(state=state, tenant_id=current_user.tenant_id)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/xero/callback")
async def xero_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    """
    OAuth callback from Xero. Browser redirect - returns RedirectResponse to frontend.
    Single org → status=syncing, background sync, redirect ?connected=xero.
    Multi-org → status=connecting, redirect ?xero_select={id} for org picker.
    """
    settings = get_settings()
    frontend_integrations = f"{settings.frontend_url}/dashboard/integrations"

    parts = state.split(":", 1)
    if len(parts) != 2:
        return RedirectResponse(url=f"{frontend_integrations}?error=invalid_state")

    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        return RedirectResponse(url=f"{frontend_integrations}?error=tenant_not_found")

    try:
        encrypted_creds_str = await xero.exchange_code(code=code, state=state, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("xero_token_exchange_failed: %s", type(exc).__name__)
        return RedirectResponse(url=f"{frontend_integrations}?error=xero_auth_failed")

    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
    except ValueError as exc:
        logger.error("xero_callback_decrypt_failed: %s", type(exc).__name__)
        return RedirectResponse(url=f"{frontend_integrations}?error=xero_auth_failed")

    try:
        connections = await xero.get_connections(creds["access_token"])
    except Exception as exc:
        logger.error("xero_get_connections_failed: %s", type(exc).__name__)
        return RedirectResponse(url=f"{frontend_integrations}?error=xero_auth_failed")

    if not connections:
        return RedirectResponse(url=f"{frontend_integrations}?error=no_xero_orgs")

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero"}
    )

    if len(connections) == 1:
        org = connections[0]
        final_creds = {
            **creds,
            "xero_tenant_id": org["tenantId"],
            "xero_tenant_name": org.get("tenantName", ""),
            "connection_id": org["id"],
        }
        final_encrypted = encrypt_credentials(final_creds, tenant_id)

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
                    "type": "xero",
                    "encrypted_credentials": final_encrypted,
                    "status": "syncing",
                    "connected_at": datetime.now(UTC),
                }
            )

        pool = await get_queue_pool()
        await pool.enqueue_job("sync_xero_connection", integration_id=integration.id, tenant_id=tenant_id)
        return RedirectResponse(url=f"{frontend_integrations}?connected=xero")

    else:
        pending_creds = {
            **creds,
            "pending_orgs": [
                {
                    "id": c["id"],
                    "tenantId": c["tenantId"],
                    "tenantName": c.get("tenantName", ""),
                    "tenantType": c.get("tenantType", ""),
                }
                for c in connections
            ],
        }
        pending_encrypted = encrypt_credentials(pending_creds, tenant_id)

        if existing:
            integration = await db.integration.update(
                where={"id": existing.id},
                data={
                    "encrypted_credentials": pending_encrypted,
                    "status": "connecting",
                },
            )
        else:
            integration = await db.integration.create(
                data={
                    "tenant_id": tenant_id,
                    "type": "xero",
                    "encrypted_credentials": pending_encrypted,
                    "status": "connecting",
                }
            )

        return RedirectResponse(url=f"{frontend_integrations}?xero_select={integration.id}")


@router.get("/integrations/xero/pending-orgs/{integration_id}")
async def xero_pending_orgs(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns pending orgs for a multi-org Xero connection awaiting org selection."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "xero", "status": "connecting"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending Xero connection found")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential error")

    pending_orgs = creds.get("pending_orgs", [])
    return standard_response(data={
        "orgs": [
            {"xero_tenant_id": org["tenantId"], "tenantName": org.get("tenantName", "")}
            for org in pending_orgs
        ]
    })


@router.post("/integrations/xero/select-tenant")
async def xero_select_tenant(
    body: SelectTenantRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    After multi-org callback, user selects which Xero org to connect.
    Validates integration belongs to this tenant, updates with selected org, starts background sync.
    """
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"id": body.integration_id, "tenant_id": tenant_id, "type": "xero"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if integration.status != "connecting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integration is not in pending org-selection state",
        )

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("xero_select_tenant_decrypt_failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential error")

    pending_orgs: list[dict] = creds.get("pending_orgs", [])
    selected = next((o for o in pending_orgs if o["tenantId"] == body.xero_tenant_id), None)
    if not selected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected tenantId not found in pending orgs",
        )

    final_creds = {
        k: v for k, v in creds.items() if k != "pending_orgs"
    }
    final_creds["xero_tenant_id"] = selected["tenantId"]
    final_creds["xero_tenant_name"] = selected.get("tenantName", "")
    final_creds["connection_id"] = selected["id"]

    final_encrypted = encrypt_credentials(final_creds, tenant_id)

    integration = await db.integration.update(
        where={"id": integration.id},
        data={
            "encrypted_credentials": final_encrypted,
            "status": "syncing",
            "connected_at": datetime.now(UTC),
        },
    )

    pool = await get_queue_pool()
    await pool.enqueue_job("sync_xero_connection", integration_id=integration.id, tenant_id=tenant_id)

    return standard_response(
        data={
            "status": "syncing",
            "integration_id": integration.id,
            "xero_tenant_id": selected["tenantId"],
            "xero_tenant_name": selected.get("tenantName", ""),
        }
    )


@router.get("/integrations/xero/status")
async def xero_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns current Xero connection status and connected_at for the authenticated tenant."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "xero"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": (
                integration.connected_at.isoformat() if integration.connected_at else None
            ),
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "integration_id": integration.id,
            "summary": integration.sync_metadata,
        }
    )


@router.post("/integrations/xero/sync")
async def xero_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a background Xero sync for the authenticated tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Xero connection found",
        )

    await db.integration.update(where={"id": integration.id}, data={"status": "syncing"})
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_xero_connection", integration_id=integration.id, tenant_id=tenant_id)
    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/xero/disconnect")
async def xero_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Xero connection and marks integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Xero connection found",
        )

    # Revoke the connection at Xero
    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        access_token = creds.get("access_token", "")
        connection_id = creds.get("connection_id", "")
        if access_token and connection_id:
            await xero.revoke_connection(access_token=access_token, connection_id=connection_id)
    except Exception as exc:
        logger.warning(
            "xero_token_revocation_failed (proceeding with disconnect): %s",
            type(exc).__name__,
        )

    # Mark disconnected regardless of revocation outcome - credentials wiped
    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
