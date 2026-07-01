from collections import defaultdict
from datetime import datetime, timedelta, UTC
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

logger = get_logger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats")
async def dashboard_stats(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Overview counts for the dashboard header cards."""
    tenant_id = current_user.tenant_id

    execution_count = await db.execution.count(where={"tenant_id": tenant_id})
    pending_approvals = await db.approval.count(where={"tenant_id": tenant_id, "status": "pending"})
    tool_count = await db.tool.count(where={"tenant_id": tenant_id, "status": "active"})
    invoice_count = await db.invoice.count(where={"tenant_id": tenant_id})
    transaction_count = await db.banktransaction.count(where={"tenant_id": tenant_id})

    return standard_response(data={
        "executions": execution_count,
        "pending_approvals": pending_approvals,
        "active_tools": tool_count,
        "invoices": invoice_count,
        "transactions": transaction_count,
    })


@router.get("/dashboard/executions")
async def list_executions(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    tool_id: str | None = Query(None),
):
    """Lists executions for the tenant, newest first. Optionally filter by tool_id."""
    tenant_id = current_user.tenant_id
    where: dict = {"tenant_id": tenant_id}
    if status:
        where["status"] = status
    if tool_id:
        where["tool_id"] = tool_id

    total = await db.execution.count(where=where)
    executions = await db.execution.find_many(
        where=where,
        order={"created_at": "desc"},
        take=limit,
        skip=offset,
        include={"tool": True, "approval": True},
    )

    return standard_response(data={
        "executions": [
            {
                "id": e.id,
                "tool_id": e.tool_id,
                "tool_type": e.tool.type if e.tool else "unknown",
                "decision": e.decision,
                "confidence": e.confidence,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at.isoformat(),
                "input_ref": e.input_ref,
                "error_message": e.error_message,
                "triggered_by_email": e.triggered_by_email,
                "approval_id": e.approval.id if e.approval else None,
            }
            for e in executions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/dashboard/executions/chart")
async def execution_chart(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    days: int = Query(7, ge=1, le=30),
):
    """Execution counts grouped by day for the last N days. Used by the dashboard chart."""
    tenant_id = current_user.tenant_id
    since = datetime.now(UTC) - timedelta(days=days)

    executions = await db.execution.find_many(
        where={"tenant_id": tenant_id, "created_at": {"gte": since}},
        order={"created_at": "asc"},
    )

    AUTO_DECISIONS = {"auto_approved", "clean"}
    PENDING_DECISIONS = {"approval_required"}

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"auto": 0, "pending": 0})
    for e in executions:
        day = e.created_at.strftime("%Y-%m-%d")
        if e.decision in AUTO_DECISIONS:
            counts[day]["auto"] += 1
        elif e.decision in PENDING_DECISIONS:
            counts[day]["pending"] += 1

    result = []
    for i in range(days):
        d = (datetime.now(UTC) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        label = (datetime.now(UTC) - timedelta(days=days - 1 - i)).strftime("%a")
        result.append({"date": d, "label": label, "auto": counts[d]["auto"], "pending": counts[d]["pending"]})

    return standard_response(data={"chart": result})


@router.get("/dashboard/approvals")
async def list_approvals(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    tool_id: str | None = Query(None),
):
    """Lists pending approvals for the tenant. Optionally filter by tool_id."""
    tenant_id = current_user.tenant_id
    where: dict = {"tenant_id": tenant_id, "status": "pending"}
    if tool_id:
        execs = await db.execution.find_many(
            where={"tenant_id": tenant_id, "tool_id": tool_id},
            take=500,
        )
        where["execution_id"] = {"in": [e.id for e in execs]}

    approvals = await db.approval.find_many(
        where=where,
        order={"requested_at": "asc"},
        take=limit,
        skip=offset,
        include={"execution": {"include": {"tool": True}}},
    )

    # Pull documents linked to these executions (document_intelligence only)
    execution_ids = [a.execution_id for a in approvals]
    documents = await db.document.find_many(
        where={"execution_id": {"in": execution_ids}},
    ) if execution_ids else []
    doc_by_exec = {d.execution_id: d for d in documents if d.execution_id}

    def _row(a) -> dict:
        exec_ = a.execution
        doc = doc_by_exec.get(a.execution_id)
        triggered_by = None
        if exec_ and exec_.triggered_by_email:
            triggered_by = exec_.triggered_by_email.split("@")[0]
        return {
            "id": a.id,
            "execution_id": a.execution_id,
            "status": a.status,
            "requested_at": a.requested_at.isoformat(),
            "expires_at": a.expires_at.isoformat(),
            "decision": exec_.decision if exec_ else None,
            "confidence": exec_.confidence if exec_ else None,
            "tool_type": exec_.tool.type if exec_ and exec_.tool else None,
            "triggered_by": triggered_by,
            "document_filename": doc.filename if doc else None,
            "document_type": doc.document_type if doc else None,
            "reason": doc.reason if doc else None,
            "rule_triggered": doc.rule_triggered if doc else None,
        }

    return standard_response(data={
        "approvals": [_row(a) for a in approvals],
        "limit": limit,
        "offset": offset,
    })


@router.get("/dashboard/audit")
async def list_audit(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    tool_id: str | None = Query(None),
):
    """Lists audit log entries for the tenant. Optionally filter by tool_id."""
    tenant_id = current_user.tenant_id
    where: dict = {"tenant_id": tenant_id}
    if tool_id:
        execs = await db.execution.find_many(
            where={"tenant_id": tenant_id, "tool_id": tool_id},
            take=500,
        )
        where["execution_id"] = {"in": [e.id for e in execs]}

    entries = await db.auditlog.find_many(
        where=where,
        order={"created_at": "desc"},
        take=limit,
        skip=offset,
    )

    return standard_response(data={
        "entries": [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "model_version": e.model_version,
                "created_at": e.created_at.isoformat(),
                "execution_id": e.execution_id,
                "reasoning_trace_json": e.reasoning_trace_json,
            }
            for e in entries
        ],
        "limit": limit,
        "offset": offset,
    })


@router.get("/dashboard/tools")
async def list_tools(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Lists all tools for the tenant."""
    tenant_id = current_user.tenant_id

    tools = await db.tool.find_many(
        where={"tenant_id": tenant_id},
        order={"type": "asc"},
    )

    return standard_response(data={
        "tools": [
            {
                "id": w.id,
                "type": w.type,
                "autonomy_level": w.autonomy_level,
                "version": w.version,
                "status": w.status,
            }
            for w in tools
        ]
    })
