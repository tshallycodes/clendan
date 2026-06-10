"""
Xero OAuth integration routes.
Flow: connect → callback (multi-org check) → [select-tenant] → sync → status / disconnect
"""
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.xero import client as xero
from app.integrations.xero.sync import enqueue_xero_sync

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
    OAuth callback from Xero.
    1. Validates state, extracts tenant_id.
    2. Exchanges code + PKCE verifier for tokens.
    3. Retrieves connected org list from Xero.
    4. Single org → store credentials, status=syncing, enqueue sync.
       Multi-org → store pending_orgs, status=connecting, return needs_org_selection=True.
    All steps are required — partial completion is a failure.
    """
    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Exchange code for tokens (PKCE verifier retrieved internally by exchange_code)
    try:
        encrypted_creds_str = await xero.exchange_code(code=code, state=state, tenant_id=tenant_id)
    except ValueError as exc:
        logger.error("xero_callback_pkce_error: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PKCE validation failed")
    except Exception as exc:
        logger.error("xero_token_exchange_failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Xero token exchange failed")

    # Decrypt to read access_token for connections call, then re-encrypt for storage
    try:
        creds = decrypt_credentials(encrypted_creds_str, tenant_id)
    except ValueError as exc:
        logger.error("xero_callback_decrypt_failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Credential handling error")

    # Fetch connected orgs from Xero
    try:
        connections = await xero.get_connections(creds["access_token"])
    except Exception as exc:
        logger.error("xero_get_connections_failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to retrieve Xero organisations")

    if not connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Xero organisations found — ensure you have connected at least one organisation",
        )

    # Upsert integration record
    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero"}
    )

    if len(connections) == 1:
        # Single org — store xero_tenant_id, begin sync immediately
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

        try:
            await enqueue_xero_sync(integration_id=integration.id, tenant_id=tenant_id)
        except Exception as exc:
            logger.warning("xero_enqueue_sync_failed: %s", type(exc).__name__)

        return standard_response(
            data={
                "status": "syncing",
                "integration_id": integration.id,
                "xero_tenant_id": org["tenantId"],
                "xero_tenant_name": org.get("tenantName", ""),
            }
        )

    else:
        # Multiple orgs — store pending_orgs, let user select
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

        orgs_public = [
            {"tenantId": c["tenantId"], "tenantName": c.get("tenantName", ""), "tenantType": c.get("tenantType", "")}
            for c in connections
        ]

        return standard_response(
            data={
                "needs_org_selection": True,
                "orgs": orgs_public,
                "pending_integration_id": integration.id,
            }
        )


@router.post("/integrations/xero/select-tenant")
async def xero_select_tenant(
    body: SelectTenantRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    After multi-org callback, user selects which Xero org to connect.
    Validates integration belongs to this tenant, updates with selected org, enqueues sync.
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

    try:
        await enqueue_xero_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("xero_select_tenant_enqueue_failed: %s", type(exc).__name__)

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
            "integration_id": integration.id,
        }
    )


@router.post("/integrations/xero/sync")
async def xero_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Enqueues a Xero sync job for the authenticated tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": "connected"}
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Xero connection found",
        )

    try:
        await enqueue_xero_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("xero_manual_sync_enqueue_failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue sync job",
        )

    return standard_response(data={"status": "sync_queued", "integration_id": integration.id})


@router.delete("/integrations/xero/disconnect")
async def xero_disconnect(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revokes Xero connection and marks integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": "connected"}
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

    # Mark disconnected regardless of revocation outcome — credentials wiped
    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
