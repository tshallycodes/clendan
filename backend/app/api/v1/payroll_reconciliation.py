"""
Payroll Reconciliation API — /v1/payroll-runs
Endpoints: list runs, trigger run, get run detail, get ghosts, get missing, export CSV.
All queries scoped to current_user.tenant_id (no cross-tenant access).
"""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

router = APIRouter(tags=["payroll-reconciliation"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RosterEmployee(BaseModel):
    name: str
    expected_minor: int

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Employee name cannot be empty")
        return v.strip()

    @field_validator("expected_minor")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("expected_minor must be a positive integer (minor currency units)")
        return v


class TriggerPayrollRunRequest(BaseModel):
    period: str  # "YYYY-MM"
    roster: list[RosterEmployee]
    tool_id: str

    @field_validator("period")
    @classmethod
    def period_format(cls, v: str) -> str:
        if len(v) != 7 or v[4] != "-":
            raise ValueError("period must be in YYYY-MM format")
        try:
            int(v[:4])
            int(v[5:])
        except ValueError as exc:
            raise ValueError("period must be in YYYY-MM format") from exc
        return v

    @field_validator("roster")
    @classmethod
    def roster_not_empty(cls, v: list[RosterEmployee]) -> list[RosterEmployee]:
        if not v:
            raise ValueError("roster cannot be empty")
        return v


# ---------------------------------------------------------------------------
# GET /v1/payroll-runs
# ---------------------------------------------------------------------------


@router.get("/payroll-runs")
async def list_payroll_runs(current_user: RequireOrgAuth) -> dict:
    """List payroll reconciliation runs for the tenant, newest first (limit 20)."""
    db = get_db()
    tenant_id = current_user.tenant_id

    runs = await db.payrollrun.find_many(
        where={"tenant_id": tenant_id},
        order={"created_at": "desc"},
        take=20,
    )

    return standard_response(data={
        "runs": [
            {
                "id": r.id,
                "period": r.period,
                "status": r.status,
                "matched_count": r.matched_count,
                "ghost_count": r.ghost_count,
                "missing_count": r.missing_count,
                "discrepancy_count": r.discrepancy_count,
                "total_payroll_minor": r.total_payroll_minor,
                "execution_id": r.execution_id,
                "created_at": r.created_at.isoformat(),
                "roster_json": r.roster_json,
            }
            for r in runs
        ]
    })


# ---------------------------------------------------------------------------
# POST /v1/payroll-runs
# ---------------------------------------------------------------------------


@router.post("/payroll-runs")
async def trigger_payroll_run(
    body: TriggerPayrollRunRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """Trigger a payroll reconciliation run. Enqueued asynchronously."""
    db = get_db()
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_first(
        where={"id": body.tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Create a placeholder PayrollRun record so callers have a run_id immediately
    roster_raw = [{"name": e.name, "expected_minor": e.expected_minor} for e in body.roster]
    run = await db.payrollrun.create(
        data={
            "tenant_id": tenant_id,
            "period": body.period,
            "status": "pending",
            "roster_json": roster_raw,
        }
    )

    execution = await db.execution.create(
        data={
            "tenant_id": tenant_id,
            "tool_id": body.tool_id,
            "input_ref": f"payroll-run:{run.id}:{uuid.uuid4().hex[:8]}",
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
            "triggered_by_email": current_user.email,
        }
    )

    await db.payrollrun.update(
        where={"id": run.id},
        data={"execution_id": execution.id},
    )

    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_payroll_rec_job",
        payroll_run_id=run.id,
        tenant_id=tenant_id,
        tool_id=body.tool_id,
        roster=roster_raw,
        period=body.period,
    )

    logger.info(
        "payroll_rec_triggered",
        extra={
            "tenant_id": tenant_id,
            "run_id": run.id,
            "period": body.period,
            "roster_size": len(body.roster),
        },
    )

    return standard_response(data={
        "run_id": run.id,
        "execution_id": execution.id,
        "status": "queued",
    })


# ---------------------------------------------------------------------------
# GET /v1/payroll-runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/payroll-runs/{run_id}")
async def get_payroll_run(run_id: str, current_user: RequireOrgAuth) -> dict:
    """Get a payroll reconciliation run with full results."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.payrollrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    return standard_response(data={
        "id": run.id,
        "period": run.period,
        "status": run.status,
        "matched_count": run.matched_count,
        "ghost_count": run.ghost_count,
        "missing_count": run.missing_count,
        "discrepancy_count": run.discrepancy_count,
        "total_payroll_minor": run.total_payroll_minor,
        "execution_id": run.execution_id,
        "results_json": run.results_json,
        "roster_json": run.roster_json,
        "created_at": run.created_at.isoformat(),
    })


# ---------------------------------------------------------------------------
# GET /v1/payroll-runs/{run_id}/ghosts
# ---------------------------------------------------------------------------


@router.get("/payroll-runs/{run_id}/ghosts")
async def get_payroll_run_ghosts(run_id: str, current_user: RequireOrgAuth) -> dict:
    """Return only ghost employees from a payroll run."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.payrollrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    results = run.results_json if isinstance(run.results_json, dict) else {}
    ghosts = results.get("ghosts", [])

    return standard_response(data={"run_id": run_id, "ghosts": ghosts, "total": len(ghosts)})


# ---------------------------------------------------------------------------
# GET /v1/payroll-runs/{run_id}/missing
# ---------------------------------------------------------------------------


@router.get("/payroll-runs/{run_id}/missing")
async def get_payroll_run_missing(run_id: str, current_user: RequireOrgAuth) -> dict:
    """Return only missing employees from a payroll run."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.payrollrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    results = run.results_json if isinstance(run.results_json, dict) else {}
    missing = results.get("missing", [])

    return standard_response(data={"run_id": run_id, "missing": missing, "total": len(missing)})


# ---------------------------------------------------------------------------
# GET /v1/payroll-runs/{run_id}/export
# ---------------------------------------------------------------------------


@router.get("/payroll-runs/{run_id}/export")
async def export_payroll_run_csv(run_id: str, current_user: RequireOrgAuth) -> StreamingResponse:
    """Export payroll reconciliation results (ghosts, missing, discrepancies) as CSV."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.payrollrun.find_first(where={"id": run_id, "tenant_id": tenant_id})
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    results = run.results_json if isinstance(run.results_json, dict) else {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["type", "name", "description", "amount", "expected_amount", "diff_pct", "date", "transaction_id"])

    for g in results.get("ghosts", []):
        writer.writerow([
            "ghost", g.get("extracted_name", ""), g.get("description", ""),
            f"{g.get('amount_minor', 0) / 100:.2f}", "", "",
            g.get("date", ""), g.get("transaction_id", ""),
        ])

    for m in results.get("missing", []):
        writer.writerow([
            "missing", m.get("name", ""), "",
            "", f"{m.get('expected_minor', 0) / 100:.2f}", "", "", "",
        ])

    for d in results.get("discrepancies", []):
        writer.writerow([
            "discrepancy", d.get("name", ""), "",
            f"{d.get('actual_minor', 0) / 100:.2f}", f"{d.get('expected_minor', 0) / 100:.2f}",
            f"{d.get('diff_pct', 0):.1f}", "", d.get("transaction_id", ""),
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="payroll_rec_{run.period}.csv"'},
    )
