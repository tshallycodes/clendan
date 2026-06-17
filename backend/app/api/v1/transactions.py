from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.categories import ALLOWED_CATEGORIES, INCOME_CATEGORIES, EXPENSE_CATEGORIES
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

logger = get_logger(__name__)
router = APIRouter(tags=["transactions"])


class CategoryUpdateRequest(BaseModel):
    category: str


@router.get("/transactions/categories")
async def list_transaction_categories(_: RequireOrgAuth):
    """Returns grouped income and expense category lists."""
    return standard_response(data={
        "income": sorted(INCOME_CATEGORIES),
        "expenses": sorted(EXPENSE_CATEGORIES),
    })


@router.get("/transactions")
async def list_all_transactions(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    status_filter: str | None = Query(None, alias="status"),
    source: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lists all bank transactions for the tenant across every connected source
    (Plaid, TrueLayer, Mono). Scoped to tenant — never leaks cross-tenant data.
    """
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id}
    if status_filter:
        where["status"] = status_filter
    if source:
        where["source"] = source

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


@router.patch("/transactions/{transaction_id}/category")
async def update_transaction_category(
    transaction_id: str,
    body: CategoryUpdateRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Updates the category for any bank transaction regardless of source.
    Works for Plaid, TrueLayer, and Mono transactions.
    """
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
    return standard_response(
        data={"id": updated.id, "ai_category": updated.ai_category, "status": updated.status}
    )
