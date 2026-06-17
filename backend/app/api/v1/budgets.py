"""
Budget CRUD routes. Tenants create budgets with line items (department + category + amount).
The Budgeting tool reads these to run variance analysis.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from app.core.db import get_db
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

router = APIRouter(prefix="/budgets", tags=["budgets"])


class _BudgetLineIn(BaseModel):
    department: str | None = None
    category: str
    amount_cents: int
    currency: str = "GBP"


class _BudgetIn(BaseModel):
    name: str
    period_start: datetime
    period_end: datetime
    lines: list[_BudgetLineIn] = []


class _BudgetLineUpdate(BaseModel):
    department: str | None = None
    category: str
    amount_cents: int
    currency: str = "GBP"


class _BudgetUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    lines: list[_BudgetLineUpdate] | None = None


def _serialise_budget(budget: Any, lines: list | None = None) -> dict:
    return {
        "id": budget.id,
        "tenant_id": budget.tenant_id,
        "name": budget.name,
        "period_start": budget.period_start.isoformat(),
        "period_end": budget.period_end.isoformat(),
        "status": budget.status,
        "created_at": budget.created_at.isoformat(),
        "lines": [
            {
                "id": ln.id,
                "department": ln.department,
                "category": ln.category,
                "amount_cents": ln.amount_cents,
                "currency": ln.currency,
            }
            for ln in (lines or [])
        ],
    }


@router.post("")
async def create_budget(current_user: RequireOrgAuth, body: _BudgetIn):
    db = get_db()
    tenant_id = current_user.tenant_id

    if body.period_end <= body.period_start:
        raise HTTPException(status_code=400, detail="period_end must be after period_start")

    if not body.lines:
        raise HTTPException(status_code=400, detail="Budget must have at least one line")

    for ln in body.lines:
        if ln.amount_cents <= 0:
            raise HTTPException(status_code=400, detail=f"amount_cents must be positive for category '{ln.category}'")

    budget = await db.budget.create(
        data={
            "tenant_id": tenant_id,
            "name": body.name,
            "period_start": body.period_start,
            "period_end": body.period_end,
            "status": "active",
        }
    )

    lines = []
    for ln in body.lines:
        line = await db.budgetline.create(
            data={
                "budget_id": budget.id,
                "department": ln.department,
                "category": ln.category,
                "amount_cents": ln.amount_cents,
                "currency": ln.currency,
            }
        )
        lines.append(line)

    return standard_response(data=_serialise_budget(budget, lines))


@router.get("")
async def list_budgets(current_user: RequireOrgAuth):
    db = get_db()
    tenant_id = current_user.tenant_id

    budgets = await db.budget.find_many(
        where={"tenant_id": tenant_id},
        include={"lines": True},
        order={"created_at": "desc"},
    )

    return standard_response(data={"budgets": [_serialise_budget(b, b.lines) for b in budgets]})


@router.get("/{budget_id}")
async def get_budget(current_user: RequireOrgAuth, budget_id: str = Path(...)):
    db = get_db()
    tenant_id = current_user.tenant_id

    budget = await db.budget.find_first(
        where={"id": budget_id, "tenant_id": tenant_id},
        include={"lines": True},
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")

    return standard_response(data=_serialise_budget(budget, budget.lines))


@router.put("/{budget_id}")
async def update_budget(
    current_user: RequireOrgAuth,
    body: _BudgetUpdate,
    budget_id: str = Path(...),
):
    db = get_db()
    tenant_id = current_user.tenant_id

    budget = await db.budget.find_first(where={"id": budget_id, "tenant_id": tenant_id})
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")

    if body.status and body.status not in ("active", "closed", "draft"):
        raise HTTPException(status_code=400, detail="status must be active, closed, or draft")

    update_data: dict = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.status is not None:
        update_data["status"] = body.status

    if update_data:
        budget = await db.budget.update(where={"id": budget_id}, data=update_data)

    if body.lines is not None:
        await db.budgetline.delete_many(where={"budget_id": budget_id})
        for ln in body.lines:
            if ln.amount_cents <= 0:
                raise HTTPException(
                    status_code=400, detail=f"amount_cents must be positive for category '{ln.category}'"
                )
            await db.budgetline.create(
                data={
                    "budget_id": budget_id,
                    "department": ln.department,
                    "category": ln.category,
                    "amount_cents": ln.amount_cents,
                    "currency": ln.currency,
                }
            )

    updated = await db.budget.find_first(
        where={"id": budget_id, "tenant_id": tenant_id},
        include={"lines": True},
    )

    return standard_response(data=_serialise_budget(updated, updated.lines if updated else []))


@router.delete("/{budget_id}")
async def close_budget(current_user: RequireOrgAuth, budget_id: str = Path(...)):
    db = get_db()
    tenant_id = current_user.tenant_id

    budget = await db.budget.find_first(where={"id": budget_id, "tenant_id": tenant_id})
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")

    await db.budget.update(where={"id": budget_id}, data={"status": "closed"})

    return standard_response(data={"id": budget_id, "status": "closed"})
