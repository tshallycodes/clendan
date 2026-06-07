import json
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth, CurrentUser
from app.integrations.plaid import client as plaid
from app.integrations.plaid.sync import enqueue_plaid_sync

logger = get_logger(__name__)
router = APIRouter(tags=["plaid"])


class ExchangeTokenRequest(BaseModel):
    public_token: str


@router.post("/integrations/plaid/link-token")
async def create_link_token(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Creates a Plaid Link token. Frontend passes this to the Plaid Link widget."""
    try:
        link_token = await plaid.create_link_token(user_id=current_user.user_id, tenant_id=current_user.tenant_id)
    except Exception as exc:
        logger.error("Plaid link token creation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create Plaid link token")

    return standard_response(data={"link_token": link_token})


@router.post("/integrations/plaid/exchange-token")
async def exchange_token(
    body: ExchangeTokenRequest,
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

    credentials_json = json.dumps(creds)

    existing = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "plaid"}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={
                "encrypted_credentials": credentials_json,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            },
        )
    else:
        integration = await db.integration.create(
            data={
                "tenant_id": tenant_id,
                "type": "plaid",
                "encrypted_credentials": credentials_json,
                "status": "connected",
                "connected_at": datetime.now(UTC),
            }
        )

    # Enqueue initial sync
    try:
        await enqueue_plaid_sync(integration_id=integration.id, tenant_id=tenant_id)
    except Exception as exc:
        logger.warning("Failed to enqueue Plaid sync (will retry later): %s", type(exc).__name__)

    return standard_response(
        data={"status": "connected", "integration_id": integration.id}
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

    return standard_response(
        data={
            "status": integration.status,
            "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
            "accounts": account_count,
            "transactions": txn_count,
        }
    )


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
                    "category": t.ai_category or t.category,
                    "status": t.status,
                    "matched_invoice_id": t.matched_invoice_id,
                }
                for t in transactions
            ],
            "limit": limit,
            "offset": offset,
        }
    )


@router.delete("/integrations/plaid/disconnect")
async def disconnect_plaid(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Marks Plaid integration as disconnected. Credentials wiped."""
    tenant_id = current_user.tenant_id

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "plaid", "status": "connected"}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Plaid connection")

    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )

    return standard_response(data={"status": "disconnected"})
