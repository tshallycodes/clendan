"""Workflow connection routes - read and toggle the auto-handoff between tools.

A connection is the edge between two consecutive tools in a workflow. Enabled means
the upstream tool auto-advances to the downstream one on a successful run. A missing
row means enabled (default on). Only known edges (see WORKFLOW_EDGES) are accepted.
"""
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import CurrentUser, RequireOrgAuth, require_role
from app.core.workflow import WORKFLOW_EDGES

logger = get_logger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])

_UNPAID_BILL_STATUSES = ["paid", "void"]


class ConnectionPatch(BaseModel):
    from_type: str
    to_type: str
    enabled: bool


def _is_known_edge(from_type: str, to_type: str) -> bool:
    edge = WORKFLOW_EDGES.get(from_type)
    return edge is not None and edge[0] == to_type


async def _edge_backlog(db, tenant_id: str, from_type: str, to_type: str) -> int | None:
    """Count records processed upstream but not yet handled downstream - i.e. what a manual
    flush would pick up. Returns None for window-based edges (recon->tax, tax->reporting),
    which re-scan a period rather than draining a per-record queue.
    """
    if from_type == "document_intelligence" and to_type == "spend_control":
        # Bills/expenses that exist but Spend Control has not assessed (control_status unset).
        # Bills: no age limit (all outstanding are assessed). Expenses: bounded by the tool's
        # unassessed catch-up limit (expense_lookback_days; 0 = no limit), so the badge counts
        # exactly what a flush would actually process.
        bills = await db.accountingbill.count(
            where={"tenant_id": tenant_id, "control_status": None,
                   "status": {"not_in": _UNPAID_BILL_STATUSES}}
        )
        exp_where: dict = {"tenant_id": tenant_id, "control_status": None}
        tool = await db.tool.find_first(where={"tenant_id": tenant_id, "type": "spend_control"})
        cfg = tool.config_json if tool and isinstance(tool.config_json, dict) else {}
        try:
            max_age = int(cfg.get("expense_lookback_days", 0) or 0)
        except (TypeError, ValueError):
            max_age = 0
        if max_age > 0:
            exp_where["expense_date"] = {"gte": datetime.now(UTC) - timedelta(days=max_age)}
        expenses = await db.accountingexpense.count(where=exp_where)
        return bills + expenses

    if from_type == "spend_control" and to_type == "payment_run":
        # Approved, still-owed bills that no scheduled/paid payment run has picked up yet.
        approved = await db.accountingbill.find_many(
            where={"tenant_id": tenant_id, "control_status": "approved",
                   "status": {"not_in": _UNPAID_BILL_STATUSES}, "outstanding_cents": {"gt": 0}}
        )
        if not approved:
            return 0
        runs = await db.paymentrun.find_many(
            where={"tenant_id": tenant_id, "status": {"in": ["scheduled", "paid"]}}
        )
        handled: set[str] = set()
        for r in runs:
            if isinstance(r.bill_ids, list):
                handled.update(r.bill_ids)
        return sum(1 for b in approved if b.id not in handled)

    return None


async def _latest_completed(db, tenant_id: str, tool_id: str):
    """Most recent execution that actually produced output (decision set, not pending/failed)."""
    return await db.execution.find_first(
        where={"tenant_id": tenant_id, "tool_id": tool_id, "decision": {"not_in": ["pending", "failed"]}},
        order={"created_at": "desc"},
    )


async def _edge_stale(db, tenant_id: str, up_tool, down_tool) -> bool:
    """For window-based edges (no per-record queue): is the downstream behind the upstream?
    True when the upstream has produced output the downstream ran before / has never seen."""
    if up_tool is None or down_tool is None:
        return False
    up = await _latest_completed(db, tenant_id, up_tool.id)
    if up is None:
        return False  # upstream has produced nothing to hand off
    down = await _latest_completed(db, tenant_id, down_tool.id)
    if down is None:
        return True  # upstream ran, downstream never has
    return up.created_at > down.created_at


@router.get("/connections")
async def list_connections(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Every workflow edge with its enabled state, the downstream tool's deploy status, and
    a backlog count (records waiting for a manual flush; null for window-based edges)."""
    tenant_id = current_user.tenant_id
    rows = await db.workflowconnection.find_many(where={"tenant_id": tenant_id})
    enabled_by_edge = {(r.from_type, r.to_type): r.enabled for r in rows}

    # Resolve one tool per type, preferring an active deployment.
    tool_by_type: dict = {}
    for t in await db.tool.find_many(where={"tenant_id": tenant_id}):
        cur = tool_by_type.get(t.type)
        if not cur or (t.status == "active" and cur.status != "active"):
            tool_by_type[t.type] = t

    connections = []
    for from_type, (to_type, _event) in WORKFLOW_EDGES.items():
        downstream = tool_by_type.get(to_type)
        backlog = await _edge_backlog(db, tenant_id, from_type, to_type)
        # Window-based edges have no per-record backlog - fall back to a staleness signal so
        # they are still flushable when the downstream is behind the upstream.
        stale = False
        if backlog is None:
            stale = await _edge_stale(db, tenant_id, tool_by_type.get(from_type), downstream)
        connections.append({
            "from_type": from_type,
            "to_type": to_type,
            "enabled": enabled_by_edge.get((from_type, to_type), True),
            "backlog": backlog,
            "downstream_stale": stale,
            "downstream_tool_id": downstream.id if downstream else None,
            "downstream_active": bool(downstream and downstream.status == "active"),
        })
    return standard_response(data={"connections": connections})


@router.patch("/connections")
async def patch_connection(
    body: ConnectionPatch,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Enable or disable a single workflow connection. Upserts the row."""
    if not _is_known_edge(body.from_type, body.to_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown workflow connection",
        )

    existing = await db.workflowconnection.find_first(
        where={
            "tenant_id": current_user.tenant_id,
            "from_type": body.from_type,
            "to_type": body.to_type,
        }
    )
    if existing:
        await db.workflowconnection.update(
            where={"id": existing.id}, data={"enabled": body.enabled}
        )
    else:
        await db.workflowconnection.create(
            data={
                "tenant_id": current_user.tenant_id,
                "from_type": body.from_type,
                "to_type": body.to_type,
                "enabled": body.enabled,
            }
        )

    logger.info(
        "workflow_connection_patched",
        extra={
            "tenant_id": current_user.tenant_id,
            "from_type": body.from_type,
            "to_type": body.to_type,
            "enabled": body.enabled,
        },
    )
    return standard_response(
        data={"from_type": body.from_type, "to_type": body.to_type, "enabled": body.enabled}
    )
