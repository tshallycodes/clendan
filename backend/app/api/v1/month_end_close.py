"""
Month-End Close API — /v1/close-runs/*
All routes require RequireOrgAuth. All queries scoped to current_user.tenant_id.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)

router = APIRouter(tags=["month-end-close"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateCloseRunRequest(BaseModel):
    period: str  # YYYY-MM

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if len(v) != 7 or v[4] != "-":
            raise ValueError("period must be in YYYY-MM format")
        try:
            year, month = int(v[:4]), int(v[5:7])
        except ValueError:
            raise ValueError("period must be in YYYY-MM format")
        if not (1 <= month <= 12):
            raise ValueError("month must be between 01 and 12")
        return v


class CompleteTaskRequest(BaseModel):
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TASK_LABELS: dict[str, str] = {
    "all_transactions_categorised": "All transactions categorised",
    "reconciliation_complete": "Reconciliation complete",
    "approvals_resolved": "All approvals resolved",
    "payroll_reconciled": "Payroll reconciled",
    "sign_offs_collected": "Sign-offs collected",
}

MANUAL_TASKS = {"payroll_reconciled", "sign_offs_collected"}


def _default_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_key": key,
            "label": label,
            "status": "pending",
            "completed_at": None,
            "completed_by": None,
            "notes": None,
        }
        for key, label in TASK_LABELS.items()
    ]


def _serialise_run(run: Any) -> dict[str, Any]:
    tasks = run.tasks_json if isinstance(run.tasks_json, list) else []
    sign_offs = run.sign_offs_json if isinstance(run.sign_offs_json, list) else []
    return {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "period": run.period,
        "status": run.status,
        "tasks": tasks,
        "sign_offs": sign_offs,
        "created_at": run.created_at.isoformat(),
        "closed_at": run.closed_at.isoformat() if run.closed_at else None,
        "closed_by_email": run.closed_by_email,
    }


def _detect_bottlenecks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tasks if t.get("status") in ("blocked", "pending")]


# ---------------------------------------------------------------------------
# GET /v1/close-runs
# ---------------------------------------------------------------------------


@router.get("/close-runs")
async def list_close_runs(current_user: RequireOrgAuth) -> dict:
    """List all MonthEndCloseRun for tenant, ordered by period desc, limit 12."""
    db = get_db()
    runs = await db.monthendcloserun.find_many(
        where={"tenant_id": current_user.tenant_id},
        order={"period": "desc"},
        take=12,
    )
    return standard_response(data={"runs": [_serialise_run(r) for r in runs]})


# ---------------------------------------------------------------------------
# POST /v1/close-runs
# ---------------------------------------------------------------------------


@router.post("/close-runs")
async def create_close_run(
    body: CreateCloseRunRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """Start a new close run for the given period. Returns 409 if one already exists."""
    db = get_db()
    tenant_id = current_user.tenant_id

    existing = await db.monthendcloserun.find_unique(
        where={"tenant_id_period": {"tenant_id": tenant_id, "period": body.period}}
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Close run for period {body.period} already exists",
        )

    run = await db.monthendcloserun.create(
        data={
            "tenant_id": tenant_id,
            "period": body.period,
            "status": "open",
            "tasks_json": _default_tasks(),
            "sign_offs_json": [],
        }
    )

    logger.info(
        "close_run_created",
        extra={"tenant_id": tenant_id, "period": body.period, "run_id": run.id},
    )

    return standard_response(data=_serialise_run(run))


# ---------------------------------------------------------------------------
# GET /v1/close-runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/close-runs/{run_id}")
async def get_close_run(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Get a close run with all task details."""
    db = get_db()
    run = await db.monthendcloserun.find_unique(where={"id": run_id})
    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Close run not found")
    return standard_response(data=_serialise_run(run))


# ---------------------------------------------------------------------------
# POST /v1/close-runs/{run_id}/refresh
# ---------------------------------------------------------------------------


@router.post("/close-runs/{run_id}/refresh")
async def refresh_close_run(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Re-evaluate auto-checkable tasks by enqueuing a job."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.monthendcloserun.find_unique(where={"id": run_id})
    if not run or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Close run not found")
    if run.status == "closed":
        raise HTTPException(status_code=409, detail="Close run is already closed")

    # Find the deployed month_end_close tool
    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": "month_end_close"}
    )
    tool_id = tool.id if tool else "system"

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_month_end_close_job",
        close_run_id=run_id,
        tenant_id=tenant_id,
        tool_id=tool_id,
    )

    logger.info(
        "close_run_refresh_enqueued",
        extra={"run_id": run_id, "tenant_id": tenant_id},
    )

    return standard_response(data={"queued": True, "run_id": run_id})


# ---------------------------------------------------------------------------
# POST /v1/close-runs/{run_id}/task/{task_key}/complete
# ---------------------------------------------------------------------------


@router.post("/close-runs/{run_id}/task/{task_key}/complete")
async def complete_task(
    run_id: str,
    task_key: str,
    body: CompleteTaskRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """Manually mark a task complete. Only allowed for manual tasks."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.monthendcloserun.find_unique(where={"id": run_id})
    if not run or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Close run not found")
    if run.status == "closed":
        raise HTTPException(status_code=409, detail="Close run is already closed")
    if task_key not in TASK_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown task: {task_key}")
    if task_key not in MANUAL_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_key} is auto-evaluated and cannot be manually completed",
        )

    tasks: list[dict[str, Any]] = (
        run.tasks_json if isinstance(run.tasks_json, list) else _default_tasks()
    )
    now_iso = datetime.now(UTC).isoformat()
    updated = False
    for task in tasks:
        if task["task_key"] == task_key:
            task["status"] = "complete"
            task["completed_at"] = now_iso
            task["completed_by"] = current_user.email
            task["notes"] = body.notes
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Task not found in run")

    # Recompute run status
    statuses = [t["status"] for t in tasks]
    if all(s == "complete" for s in statuses):
        run_status = "closed"
    elif any(s == "complete" for s in statuses):
        run_status = "in_progress"
    else:
        run_status = "open"

    updated_run = await db.monthendcloserun.update(
        where={"id": run_id},
        data={
            "tasks_json": tasks,
            "status": run_status,
            "closed_at": datetime.now(UTC) if run_status == "closed" else None,
            "closed_by_email": current_user.email if run_status == "closed" else None,
        },
    )

    logger.info(
        "close_task_completed",
        extra={"run_id": run_id, "task_key": task_key, "tenant_id": tenant_id},
    )

    return standard_response(data=_serialise_run(updated_run))


# ---------------------------------------------------------------------------
# POST /v1/close-runs/{run_id}/sign-off
# ---------------------------------------------------------------------------


@router.post("/close-runs/{run_id}/sign-off")
async def add_sign_off(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Add current user email to sign_offs_json. Returns 409 if already signed."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.monthendcloserun.find_unique(where={"id": run_id})
    if not run or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Close run not found")
    if run.status == "closed":
        raise HTTPException(status_code=409, detail="Close run is already closed")

    sign_offs: list[dict[str, Any]] = (
        run.sign_offs_json if isinstance(run.sign_offs_json, list) else []
    )
    email = current_user.email
    if any(s.get("email") == email for s in sign_offs):
        raise HTTPException(status_code=409, detail="You have already signed off on this run")

    sign_offs.append({"email": email, "signed_at": datetime.now(UTC).isoformat()})

    # Check if sign_offs_collected task should be marked complete
    tasks: list[dict[str, Any]] = (
        run.tasks_json if isinstance(run.tasks_json, list) else _default_tasks()
    )
    for task in tasks:
        if task["task_key"] == "sign_offs_collected":
            task["status"] = "complete"
            task["completed_at"] = datetime.now(UTC).isoformat()
            task["completed_by"] = email
            break

    statuses = [t["status"] for t in tasks]
    if all(s == "complete" for s in statuses):
        run_status = "closed"
    elif any(s == "complete" for s in statuses):
        run_status = "in_progress"
    else:
        run_status = "open"

    updated_run = await db.monthendcloserun.update(
        where={"id": run_id},
        data={
            "sign_offs_json": sign_offs,
            "tasks_json": tasks,
            "status": run_status,
            "closed_at": datetime.now(UTC) if run_status == "closed" else None,
            "closed_by_email": email if run_status == "closed" else None,
        },
    )

    logger.info(
        "close_run_sign_off_added",
        extra={"run_id": run_id, "email": email, "tenant_id": tenant_id},
    )

    return standard_response(data=_serialise_run(updated_run))


# ---------------------------------------------------------------------------
# GET /v1/close-runs/{run_id}/bottlenecks
# ---------------------------------------------------------------------------


@router.get("/close-runs/{run_id}/bottlenecks")
async def get_bottlenecks(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Return list of blocking or incomplete tasks."""
    db = get_db()
    run = await db.monthendcloserun.find_unique(where={"id": run_id})
    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Close run not found")

    tasks: list[dict[str, Any]] = (
        run.tasks_json if isinstance(run.tasks_json, list) else _default_tasks()
    )
    bottlenecks = _detect_bottlenecks(tasks)

    return standard_response(data={"bottlenecks": bottlenecks, "count": len(bottlenecks)})
