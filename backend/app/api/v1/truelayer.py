import secrets
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.oauth_html import connected_page
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.truelayer import client as tl
from app.integrations.truelayer.sync import sync_truelayer_connection

logger = get_logger(__name__)
router = APIRouter(tags=["truelayer"])


@router.get("/integrations/truelayer/connect")
async def truelayer_connect(current_user: RequireOrgAuth):
    """Returns a TrueLayer OAuth authorisation URL. The frontend redirects the user there."""
    tenant_id = current_user.tenant_id
    random_part = secrets.token_urlsafe(16)
    state = f"{tenant_id}:{random_part}"
    auth_url = tl.build_auth_url(state=state)
    return standard_response(data={"auth_url": auth_url, "state": state})


@router.get("/integrations/truelayer/callback")
async def truelayer_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: Annotated[Prisma, Depends(get_db_dep)] = None,
):
    """
    OAuth2 callback from TrueLayer. Exchanges code for tokens, stores encrypted credentials,
    enqueues initial sync, then redirects the browser back to the frontend integrations page.
    """
    settings = get_settings()
    frontend_integrations = f"{settings.frontend_url}/dashboard/integrations"

    if ":" not in state:
        return RedirectResponse(url=f"{frontend_integrations}?error=invalid_state")

    tenant_id, _ = state.split(":", 1)
    if not tenant_id:
        return RedirectResponse(url=f"{frontend_integrations}?error=missing_tenant")

    try:
        token_data = await tl.exchange_code(code=code, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("TrueLayer token exchange failed for tenant %s: %s", tenant_id, type(exc).__name__)
        return RedirectResponse(url=f"{frontend_integrations}?error=truelayer_auth_failed")

    encrypted_credentials = token_data["encrypted_credentials"]

    # Fetch institution name immediately using the fresh access token
    access_token = token_data.get("access_token", "")
    institution_name = None
    if access_token:
        try:
            provider_info = await tl.get_provider_info(access_token)
            provider = provider_info.get("provider") or {}
            institution_name = (
                provider.get("display_name")
                or provider.get("provider_id")
                or provider_info.get("provider_id")
            )
        except Exception:
            pass

    # Always create a new integration — dedup happens after sync based on account IDs
    integration = await db.integration.create(
        data={
            "tenant_id": tenant_id,
            "type": "truelayer",
            "encrypted_credentials": encrypted_credentials,
            "status": "syncing",
            "institution_name": institution_name,
            "connected_at": datetime.now(UTC),
        }
    )

    background_tasks.add_task(sync_truelayer_connection, {}, integration.id, tenant_id)
    display_name = institution_name or "TrueLayer"
    return connected_page(display_name, f"{frontend_integrations}?connected=truelayer")


@router.get("/integrations/truelayer/status")
async def truelayer_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns TrueLayer connection status, account count, and transaction count."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer", "status": {"not": "disconnected"}},
        order={"connected_at": "desc"},
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    account_count = await db.bankaccount.count(where={"tenant_id": tenant_id, "source": "truelayer"})
    txn_count = await db.banktransaction.count(where={"tenant_id": tenant_id, "source": "truelayer"})

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


@router.get("/integrations/truelayer/accounts")
async def list_truelayer_accounts(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Lists TrueLayer-sourced bank accounts for the tenant."""
    accounts = await db.bankaccount.find_many(
        where={"tenant_id": current_user.tenant_id, "source": "truelayer"},
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


@router.get("/integrations/truelayer/transactions")
async def list_truelayer_transactions(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Lists TrueLayer-sourced transactions for the tenant."""
    tenant_id = current_user.tenant_id
    where = {"tenant_id": tenant_id, "source": "truelayer"}

    transactions = await db.banktransaction.find_many(
        where=where,
        order={"date": "desc"},
        take=limit,
        skip=offset,
    )
    total = await db.banktransaction.count(where=where)

    return standard_response(
        data={
            "transactions": [
                {
                    "id": t.id,
                    "amount_minor": t.amount_minor,
                    "currency": t.currency,
                    "merchant_name": t.merchant_name,
                    "description": t.description,
                    "date": t.date.isoformat(),
                    "ai_category": t.ai_category,
                    "category": t.category,
                    "status": t.status,
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/integrations/truelayer/sync")
async def trigger_truelayer_sync(
    background_tasks: BackgroundTasks,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a TrueLayer sync as a background task."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "truelayer", "status": {"not": "disconnected"}},
        order={"connected_at": "desc"},
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No TrueLayer integration found")

    await db.integration.update(where={"id": integration.id}, data={"status": "syncing"})
    background_tasks.add_task(sync_truelayer_connection, {}, integration.id, tenant_id)
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/truelayer/disconnect")
async def disconnect_truelayer(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks all non-disconnected TrueLayer integrations for the tenant as disconnected."""
    tenant_id = current_user.tenant_id

    result = await db.integration.update_many(
        where={"tenant_id": tenant_id, "type": "truelayer", "status": {"not": "disconnected"}},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    if result.count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active TrueLayer integration found")

    return standard_response(data={"status": "disconnected", "count": result.count})


@router.get("/integrations/truelayer/connections")
async def list_truelayer_connections(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    institution_name: str | None = Query(None),
):
    """Lists all TrueLayer connections for the tenant, optionally filtered by institution name."""
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id, "type": "truelayer", "status": {"not": "disconnected"}}
    if institution_name:
        where["institution_name"] = {"contains": institution_name, "mode": "insensitive"}

    integrations = await db.integration.find_many(
        where=where,
        order={"connected_at": "desc"},
    )

    connections = []
    for intg in integrations:
        accounts = await db.bankaccount.find_many(
            where={"integration_id": intg.id},
        )
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


@router.post("/integrations/truelayer/connections/{integration_id}/sync")
async def sync_truelayer_connection_endpoint(
    integration_id: str,
    background_tasks: BackgroundTasks,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a sync for a specific TrueLayer connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "truelayer"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TrueLayer connection not found")
    if intg.status == "disconnected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is disconnected — reconnect first")

    await db.integration.update(where={"id": integration_id}, data={"status": "syncing"})
    background_tasks.add_task(sync_truelayer_connection, {}, integration_id, tenant_id)
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration_id})


@router.delete("/integrations/truelayer/connections/{integration_id}")
async def disconnect_truelayer_connection(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Disconnects a specific TrueLayer connection. Credentials wiped."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "truelayer"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TrueLayer connection not found")
    if intg.status == "disconnected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already disconnected")

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    return standard_response(data={"status": "disconnected"})


@router.get("/integrations/truelayer/connections/{integration_id}/sync-log")
async def truelayer_connection_sync_log(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(20, le=100),
):
    """Returns sync log entries for a specific TrueLayer connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "truelayer"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TrueLayer connection not found")

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
