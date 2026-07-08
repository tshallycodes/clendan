import json
import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from prisma import Prisma

from app.core.bank_cleanup import cleanup_integration_data
from app.core.config import get_settings
from app.core.constants import ConnectorType, IntegrationStatus, Pagination
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.mono import client as mono
from app.integrations.mono.sync import enqueue_mono_sync

logger = get_logger(__name__)
router = APIRouter(tags=["mono"])


@router.get("/integrations/mono/connect")
async def mono_connect(current_user: RequireOrgAuth):
    """
    Creates a Mono Connect session and returns the hosted Connect URL.
    Frontend redirects the user there; Mono redirects back to /mono/callback.
    """
    tenant_id = current_user.tenant_id
    settings = get_settings()

    nonce = secrets.token_urlsafe(16)
    state = f"{tenant_id}:{nonce}"
    redirect_url = (
        f"{settings.backend_base_url}/v1/integrations/mono/callback?state={state}"
    )

    try:
        session = await mono.initiate_connect_session(
            tenant_id=tenant_id,
            redirect_url=redirect_url,
        )
    except Exception as exc:
        import httpx as _httpx
        detail = str(exc)
        if isinstance(exc, _httpx.HTTPStatusError):
            detail = f"Mono API {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error("Mono connect session failed tenant=%s detail=%s", tenant_id, detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )

    return standard_response(data={"auth_url": session["mono_url"]})


@router.get("/integrations/mono/callback")
async def mono_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Annotated[Prisma, Depends(get_db_dep)] = None,
):
    """
    Mono Connect callback. Exchanges the one-time code for an account ID,
    stores encrypted credentials, enqueues initial sync, redirects to frontend.
    """
    settings = get_settings()
    frontend_integrations = f"{settings.frontend_url}/dashboard/integrations"

    if ":" not in state:
        return RedirectResponse(url=f"{frontend_integrations}?error=invalid_state")

    tenant_id, _ = state.split(":", 1)
    if not tenant_id:
        return RedirectResponse(url=f"{frontend_integrations}?error=missing_tenant")

    try:
        encrypted_account_id = await mono.exchange_code(code)
    except Exception as exc:
        logger.error("Mono code exchange failed for tenant %s: %s", tenant_id, type(exc).__name__)
        return RedirectResponse(url=f"{frontend_integrations}?error=mono_auth_failed")

    credentials_json = json.dumps({"account_id": encrypted_account_id})

    integration = await db.integration.create(
        data={
            "tenant_id": tenant_id,
            "type": ConnectorType.MONO,
            "encrypted_credentials": credentials_json,
            "status": IntegrationStatus.SYNCING,
            "connected_at": datetime.now(UTC),
        }
    )

    await enqueue_mono_sync(integration.id, tenant_id)
    return RedirectResponse(url=f"{frontend_integrations}?connected=mono")


@router.get("/integrations/mono/status")
async def mono_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Mono connection status, account count, and transaction count."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": ConnectorType.MONO, "status": {"not": IntegrationStatus.DISCONNECTED}},
        order={"connected_at": "desc"},
    )
    if not integration:
        return standard_response(data={"status": IntegrationStatus.NOT_CONNECTED})

    account_count = await db.bankaccount.count(
        where={"tenant_id": tenant_id, "source": ConnectorType.MONO}
    )
    txn_count = await db.banktransaction.count(
        where={"tenant_id": tenant_id, "source": ConnectorType.MONO}
    )

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "institution_name": integration.institution_name,
            "accounts": account_count,
            "transactions": txn_count,
        }
    )


@router.get("/integrations/mono/accounts")
async def list_mono_accounts(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Lists Mono-sourced bank accounts for the tenant."""
    accounts = await db.bankaccount.find_many(
        where={"tenant_id": current_user.tenant_id, "source": ConnectorType.MONO},
        order={"created_at": "asc"},
    )
    return standard_response(data=[
        {
            "id": a.id,
            "name": a.name,
            "type": a.type,
            "subtype": a.subtype or "",
            "current_balance_minor": a.current_balance_minor,
            "currency": a.currency,
        }
        for a in accounts
    ])


@router.get("/integrations/mono/transactions")
async def list_mono_transactions(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(Pagination.DEFAULT_LIMIT, le=Pagination.MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Lists Mono-sourced transactions for the tenant."""
    tenant_id = current_user.tenant_id
    where: dict = {"tenant_id": tenant_id, "source": ConnectorType.MONO}
    if status_filter:
        where["status"] = status_filter

    transactions = await db.banktransaction.find_many(
        where=where,
        order={"date": "desc"},
        take=limit,
        skip=offset,
        include={"account": True},
    )
    total = await db.banktransaction.count(where=where)

    return standard_response(
        data={
            "transactions": [
                {
                    "id": t.id,
                    "source": t.source,
                    "amount_minor": t.amount_minor,
                    "currency": t.currency,
                    "merchant_name": t.merchant_name,
                    "description": t.description,
                    "date": t.date.isoformat(),
                    "ai_category": t.ai_category,
                    "plaid_category": t.category,
                    "status": t.status,
                    "matched_invoice_id": t.matched_invoice_id,
                    "account_id": t.account_id,
                    "account_name": t.account.name if t.account else None,
                    "account_subtype": t.account.subtype if t.account else None,
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/integrations/mono/sync")
async def trigger_mono_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Enqueues a Mono transaction sync via arq worker."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": ConnectorType.MONO, "status": {"not": IntegrationStatus.DISCONNECTED}},
        order={"connected_at": "desc"},
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Mono integration found")

    await db.integration.update(where={"id": integration.id}, data={"status": IntegrationStatus.SYNCING})
    await enqueue_mono_sync(integration.id, tenant_id)
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/mono/disconnect")
async def disconnect_mono(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks the Mono integration as disconnected and wipes stored credentials."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": ConnectorType.MONO, "status": {"not": IntegrationStatus.DISCONNECTED}},
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Mono connection")

    cleaned = await cleanup_integration_data(db, integration.id)
    await db.integration.update(
        where={"id": integration.id},
        data={"status": IntegrationStatus.DISCONNECTED, "encrypted_credentials": "{}"},
    )
    return standard_response(data={"status": IntegrationStatus.DISCONNECTED, **cleaned})


@router.get("/integrations/mono/connections")
async def list_mono_connections(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    institution_name: str | None = Query(None),
):
    """Lists all Mono connections for the tenant, optionally filtered by institution name."""
    tenant_id = current_user.tenant_id

    where: dict = {
        "tenant_id": tenant_id,
        "type": ConnectorType.MONO,
        "status": {"not": IntegrationStatus.DISCONNECTED},
    }
    if institution_name:
        where["institution_name"] = {"contains": institution_name, "mode": "insensitive"}

    integrations = await db.integration.find_many(
        where=where,
        include={"bank_accounts": True},
        order={"connected_at": "desc"},
    )

    connections = []
    for intg in integrations:
        accounts = intg.bank_accounts or []
        account_ids = [a.id for a in accounts]
        recent_txns = []
        if account_ids:
            recent_txns = await db.banktransaction.find_many(
                where={"account_id": {"in": account_ids}},
                order={"date": "desc"},
                take=5,
            )
        connections.append({
            "integration_id": intg.id,
            "institution_id": intg.institution_id,
            "institution_name": intg.institution_name,
            "status": intg.status,
            "connected_at": intg.connected_at.isoformat() if intg.connected_at else None,
            "last_synced_at": intg.last_synced_at.isoformat() if intg.last_synced_at else None,
            "accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.type,
                    "subtype": a.subtype or "",
                    "current_balance_minor": a.current_balance_minor,
                    "currency": a.currency,
                }
                for a in accounts
            ],
            "recent_transactions": [
                {
                    "id": t.id,
                    "merchant_name": t.merchant_name,
                    "description": t.description,
                    "amount_minor": t.amount_minor,
                    "currency": t.currency,
                    "date": t.date.isoformat(),
                    "ai_category": t.ai_category,
                }
                for t in recent_txns
            ],
        })

    return standard_response(data={"connections": connections})


@router.post("/integrations/mono/connections/{integration_id}/sync")
async def sync_mono_connection(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a sync for a specific Mono connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": ConnectorType.MONO}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mono connection not found")
    if intg.status == IntegrationStatus.DISCONNECTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is disconnected - reconnect first")

    await db.integration.update(where={"id": integration_id}, data={"status": IntegrationStatus.SYNCING})
    await enqueue_mono_sync(integration_id, tenant_id)
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration_id})


@router.delete("/integrations/mono/connections/{integration_id}")
async def disconnect_mono_connection(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Disconnects a specific Mono connection and wipes credentials."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": ConnectorType.MONO}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mono connection not found")
    if intg.status == IntegrationStatus.DISCONNECTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already disconnected")

    cleaned = await cleanup_integration_data(db, integration_id)
    await db.integration.update(
        where={"id": integration_id},
        data={"status": IntegrationStatus.DISCONNECTED, "encrypted_credentials": "{}"},
    )
    return standard_response(data={"status": IntegrationStatus.DISCONNECTED, **cleaned})


@router.get("/integrations/mono/connections/{integration_id}/sync-log")
async def mono_connection_sync_log(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(Pagination.MAX_SYNC_LOG_LIMIT, le=100),
):
    """Returns sync log entries for a specific Mono connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": ConnectorType.MONO}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mono connection not found")

    logs = await db.integrationsynclog.find_many(
        where={"integration_id": integration_id, "tenant_id": tenant_id},
        order={"created_at": "desc"},
        take=limit,
    )
    return standard_response(data=[
        {
            "id": l.id,
            "entity_type": l.entity_type,
            "status": l.status,
            "records_synced": l.records_synced,
            "error_message": l.error_message,
            "timestamp": l.created_at.isoformat(),
        }
        for l in logs
    ])
