from datetime import date, datetime
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
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
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
    date_filter: dict = {}
    if from_date:
        date_filter["gte"] = datetime(from_date.year, from_date.month, from_date.day)
    if to_date:
        date_filter["lte"] = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59)
    if date_filter:
        where["date"] = date_filter

    import asyncio
    transactions, total, all_debits, all_credits = await asyncio.gather(
        db.banktransaction.find_many(
            where=where,
            order={"date": "desc"},
            take=limit,
            skip=offset,
            include={"account": {"include": {"integration": True}}},
        ),
        db.banktransaction.count(where=where),
        db.banktransaction.find_many(where={**where, "amount_minor": {"gt": 0}}),
        db.banktransaction.find_many(where={**where, "amount_minor": {"lt": 0}}),
    )
    total_out_minor: int = sum(t.amount_minor for t in all_debits)
    total_in_minor: int = sum(-t.amount_minor for t in all_credits)

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
                    "institution_name": (
                        t.account.integration.institution_name
                        if t.account and t.account.integration
                        else None
                    ),
                }
                for t in transactions
            ],
            "total": total,
            "total_out_minor": total_out_minor,
            "total_in_minor": total_in_minor,
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

    # Log correction for AI learning — only when the category actually changed
    original_category = txn.ai_category
    if original_category and original_category != body.category:
        await db.categorycorrection.create(
            data={
                "tenant_id": current_user.tenant_id,
                "transaction_id": transaction_id,
                "original_category": original_category,
                "corrected_category": body.category,
                "merchant_name": txn.merchant_name,
                "description": txn.description,
            }
        )

    return standard_response(
        data={"id": updated.id, "ai_category": updated.ai_category, "status": updated.status}
    )
