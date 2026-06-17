import json
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.plaid import client as plaid
from app.integrations.plaid.sync import sync_plaid_transactions

logger = get_logger(__name__)
router = APIRouter(tags=["plaid"])


ALLOWED_CATEGORIES = frozenset({
    "advertising", "bank_fees", "consulting", "equipment", "insurance",
    "legal", "meals", "office_supplies", "payroll", "rent", "software",
    "tax", "travel", "utilities", "other",
})


class ExchangeTokenRequest(BaseModel):
    public_token: str
    institution_id: str | None = None
    institution_name: str | None = None


class LinkTokenRequest(BaseModel):
    institution_id: str | None = None


class CategoryUpdateRequest(BaseModel):
    category: str


@router.post("/integrations/plaid/link-token")
async def create_link_token(
    body: LinkTokenRequest,
    current_user: RequireOrgAuth,
):
    """Creates a Plaid Link token. Frontend passes this to the Plaid Link widget."""
    try:
        link_token = await plaid.create_link_token(
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
            institution_id=body.institution_id,
        )
    except Exception as exc:
        logger.error("Plaid link token creation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create Plaid link token")

    return standard_response(data={"link_token": link_token})


@router.post("/integrations/plaid/exchange-token")
async def exchange_token(
    body: ExchangeTokenRequest,
    background_tasks: BackgroundTasks,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Exchanges Plaid public_token for access_token. Stores encrypted credentials.
    Triggers initial transaction sync via background job.
    All steps required — partial completion is a failure.
    """
    tenant_id = current_user.tenant_id

    try:
        creds = await plaid.exchange_public_token(body.public_token)
    except Exception as exc:
        logger.error("Plaid token exchange failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Plaid token exchange failed")

    credentials_json = json.dumps({
        **creds,
        "institution_id": body.institution_id,
        "institution_name": body.institution_name,
    })

    # Always create a new integration — dedup happens after sync based on account IDs
    integration = await db.integration.create(
        data={
            "tenant_id": tenant_id,
            "type": "plaid",
            "institution_id": body.institution_id,
            "institution_name": body.institution_name,
            "encrypted_credentials": credentials_json,
            "status": "syncing",
            "connected_at": datetime.now(UTC),
        }
    )

    background_tasks.add_task(sync_plaid_transactions, {}, integration.id, tenant_id)

    return standard_response(
        data={"status": "syncing", "integration_id": integration.id}
    )


@router.get("/integrations/plaid/status")
async def plaid_status(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns Plaid connection status and transaction count for the tenant."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "plaid"}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})

    txn_count = await db.banktransaction.count(where={"tenant_id": tenant_id})
    account_count = await db.bankaccount.count(where={"tenant_id": tenant_id})

    creds = json.loads(integration.encrypted_credentials or '{}')
    institution_id = creds.get('institution_id')
    institution_name = creds.get('institution_name')

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
            "institution_id": institution_id,
            "institution_name": institution_name,
            "accounts": account_count,
            "transactions": txn_count,
        }
    )


@router.get("/integrations/plaid/accounts")
async def list_accounts(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Lists bank accounts for the tenant."""
    accounts = await db.bankaccount.find_many(
        where={"tenant_id": current_user.tenant_id},
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


@router.get("/integrations/plaid/transactions")
async def list_transactions(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Lists bank transactions for the tenant. Scoped to tenant — never leaks cross-tenant data."""
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id}
    if status_filter:
        where["status"] = status_filter

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
                    "plaid_category": t.category,
                    "status": t.status,
                    "matched_invoice_id": t.matched_invoice_id,
                }
                for t in transactions
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.patch("/integrations/plaid/transactions/{transaction_id}/category")
async def update_transaction_category(
    transaction_id: str,
    body: CategoryUpdateRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Manually correct an AI-assigned category. Only updates transactions owned by this tenant."""
    if body.category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Allowed: {sorted(ALLOWED_CATEGORIES)}",
        )

    txn = await db.banktransaction.find_first(
        where={"id": transaction_id, "tenant_id": current_user.tenant_id}
    )
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    updated = await db.banktransaction.update(
        where={"id": transaction_id},
        data={"ai_category": body.category, "status": "categorised"},
    )
    return standard_response(data={"id": updated.id, "ai_category": updated.ai_category, "status": updated.status})


@router.post("/integrations/plaid/sync")
async def plaid_sync(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers an inline Plaid transaction sync. Used by the Resync button."""
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": "plaid", "status": "connected"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No connected Plaid integration found")

    from app.integrations.plaid.sync import sync_plaid_transactions
    result = await sync_plaid_transactions(
        ctx={},
        integration_id=integration.id,
        tenant_id=current_user.tenant_id,
    )
    return standard_response(data={"result": result, "integration_id": integration.id})


@router.delete("/integrations/plaid/disconnect")
async def disconnect_plaid(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks Plaid integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "plaid", "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Plaid connection")

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})


@router.get("/integrations/plaid/connections")
async def list_plaid_connections(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    institution_name: str | None = Query(None),
):
    """Lists all Plaid connections for the tenant, optionally filtered by institution name (substring)."""
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id, "type": "plaid", "status": {"not": "disconnected"}}
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


@router.post("/integrations/plaid/connections/{integration_id}/sync")
async def sync_plaid_connection(
    integration_id: str,
    background_tasks: BackgroundTasks,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Triggers a sync for a specific Plaid connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "plaid"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plaid connection not found")
    if intg.status == "disconnected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection is disconnected — reconnect first")

    await db.integration.update(where={"id": integration_id}, data={"status": "syncing"})
    background_tasks.add_task(sync_plaid_transactions, {}, integration_id, tenant_id)
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration_id})


@router.delete("/integrations/plaid/connections/{integration_id}")
async def disconnect_plaid_connection(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Disconnects a specific Plaid connection. Credentials wiped."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "plaid"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plaid connection not found")
    if intg.status == "disconnected":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already disconnected")

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    return standard_response(data={"status": "disconnected"})


@router.get("/integrations/plaid/connections/{integration_id}/sync-log")
async def plaid_connection_sync_log(
    integration_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(20, le=100),
):
    """Returns sync log entries for a specific Plaid connection."""
    tenant_id = current_user.tenant_id
    intg = await db.integration.find_first(
        where={"id": integration_id, "tenant_id": tenant_id, "type": "plaid"}
    )
    if not intg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plaid connection not found")

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
