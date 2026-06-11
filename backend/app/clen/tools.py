"""
Tool executor for Clen account mode.
Tool schema definitions live in tools_defs.py.
All tools are tenant-scoped. Action tools write audit log before mutating DB.
"""
from datetime import datetime, UTC, timedelta
from typing import Any, Optional

from prisma import Prisma

from app.audit.logger import write_audit_log
from app.core.logging import get_logger
from app.clen.tools_defs import ACCOUNT_TOOLS  # re-exported for callers

logger = get_logger(__name__)

CLEN_MODEL_VERSION = "clen/1.0"

__all__ = ["ACCOUNT_TOOLS", "execute_tool"]


# ---------------------------------------------------------------------------
# Period helper
# ---------------------------------------------------------------------------

def _period_to_datetime(period: str) -> datetime:
    """Converts a period string like '7d' to a UTC datetime cutoff."""
    days_map = {"1d": 1, "7d": 7, "30d": 30}
    days = days_map.get(period, 7)
    return datetime.now(UTC) - timedelta(days=days)


# ---------------------------------------------------------------------------
# Public executor
# ---------------------------------------------------------------------------

async def execute_tool(
    name: str,
    input: dict[str, Any],
    tenant_id: str,
    user_id: Optional[str],
    db: Prisma,
) -> dict[str, Any]:
    """
    Dispatches a tool call by name. All results are plain serialisable dicts.
    Exceptions are caught and returned as {"error": "plain english description"}.
    """
    try:
        return await _dispatch(name, input, tenant_id, user_id, db)
    except Exception as exc:
        logger.error("clen_tool_failed tool=%s tenant=%s error=%s", name, tenant_id, type(exc).__name__)
        return {"error": f"Tool '{name}' failed — please try again or contact support"}


async def _dispatch(
    name: str,
    input: dict[str, Any],
    tenant_id: str,
    user_id: Optional[str],
    db: Prisma,
) -> dict[str, Any]:
    match name:
        case "get_pending_approvals":
            return await _get_pending_approvals(tenant_id, db)
        case "get_execution_detail":
            return await _get_execution_detail(input.get("execution_id", ""), tenant_id, db)
        case "get_audit_trail":
            return await _get_audit_trail(
                tenant_id, db,
                worker_type=input.get("worker_type"),
                status=input.get("status"),
                limit=min(int(input.get("limit", 10)), 50),
            )
        case "get_execution_stats":
            return await _get_execution_stats(tenant_id, db, period=input.get("period", "7d"))
        case "list_workers":
            return await _list_workers(tenant_id, db)
        case "get_worker_status":
            return await _get_worker_status(input.get("worker_type", ""), tenant_id, db)
        case "list_integrations":
            return await _list_integrations(tenant_id, db)
        case "get_integration_status":
            return await _get_integration_status(input.get("integration_type", ""), tenant_id, db)
        case "approve_execution":
            return await _approve_execution(
                input.get("approval_id", ""), input.get("note", ""), tenant_id, user_id, db
            )
        case "reject_execution":
            return await _reject_execution(
                input.get("approval_id", ""), input.get("reason", ""), tenant_id, user_id, db
            )
        case "pause_worker":
            return await _pause_worker(input.get("worker_type", ""), tenant_id, user_id, db)
        case _:
            return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

async def _get_pending_approvals(tenant_id: str, db: Prisma) -> dict:
    approvals = await db.approval.find_many(
        where={"tenant_id": tenant_id, "status": "pending"},
        order={"requested_at": "asc"},
        include={"execution": True},
    )
    return {
        "approvals": [
            {
                "id": a.id,
                "execution_id": a.execution_id,
                "status": a.status,
                "requested_at": a.requested_at.isoformat(),
                "expires_at": a.expires_at.isoformat(),
                "decision": a.execution.decision if a.execution else None,
                "confidence": a.execution.confidence if a.execution else None,
            }
            for a in approvals
        ],
        "count": len(approvals),
    }


async def _get_execution_detail(execution_id: str, tenant_id: str, db: Prisma) -> dict:
    if not execution_id:
        return {"error": "execution_id is required"}
    execution = await db.execution.find_first(
        where={"id": execution_id, "tenant_id": tenant_id},
        include={"worker": True, "approval": True},
    )
    if not execution:
        return {"error": f"Execution {execution_id} not found"}
    return {
        "id": execution.id,
        "worker_id": execution.worker_id,
        "worker_type": execution.worker.type if execution.worker else "unknown",
        "decision": execution.decision,
        "confidence": execution.confidence,
        "status": execution.status,
        "duration_ms": execution.duration_ms,
        "input_ref": execution.input_ref,
        "created_at": execution.created_at.isoformat(),
        "approval_id": execution.approval.id if execution.approval else None,
    }


async def _get_audit_trail(
    tenant_id: str,
    db: Prisma,
    worker_type: Optional[str],
    status: Optional[str],
    limit: int,
) -> dict:
    where: dict[str, Any] = {"tenant_id": tenant_id}
    if worker_type or status:
        execution_filter: dict[str, Any] = {}
        if status:
            execution_filter["status"] = status
        if worker_type:
            execution_filter["worker"] = {"is": {"type": worker_type}}
        where["execution"] = {"is": execution_filter}
    entries = await db.auditlog.find_many(
        where=where,
        order={"created_at": "desc"},
        take=limit,
    )
    return {
        "entries": [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "model_version": e.model_version,
                "execution_id": e.execution_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "count": len(entries),
    }


async def _get_execution_stats(tenant_id: str, db: Prisma, period: str) -> dict:
    since = _period_to_datetime(period)
    executions = await db.execution.find_many(
        where={"tenant_id": tenant_id, "created_at": {"gte": since}},
    )
    counts: dict[str, int] = {}
    for e in executions:
        counts[e.decision] = counts.get(e.decision, 0) + 1
    return {
        "period": period,
        "since": since.isoformat(),
        "total": len(executions),
        "by_decision": counts,
    }


async def _list_workers(tenant_id: str, db: Prisma) -> dict:
    workers = await db.worker.find_many(
        where={"tenant_id": tenant_id},
        order={"type": "asc"},
    )
    return {
        "workers": [
            {
                "id": w.id,
                "type": w.type,
                "status": w.status,
                "autonomy_level": w.autonomy_level,
                "version": w.version,
            }
            for w in workers
        ],
        "count": len(workers),
    }


async def _get_worker_status(worker_type: str, tenant_id: str, db: Prisma) -> dict:
    if not worker_type:
        return {"error": "worker_type is required"}
    worker = await db.worker.find_first(where={"tenant_id": tenant_id, "type": worker_type})
    if not worker:
        return {"error": f"Worker type '{worker_type}' not found"}
    return {
        "id": worker.id,
        "type": worker.type,
        "status": worker.status,
        "autonomy_level": worker.autonomy_level,
        "version": worker.version,
    }


async def _list_integrations(tenant_id: str, db: Prisma) -> dict:
    integrations = await db.integration.find_many(
        where={"tenant_id": tenant_id},
        order={"type": "asc"},
    )
    return {
        "integrations": [
            {
                "id": i.id,
                "type": i.type,
                "status": i.status,
                "connected_at": i.connected_at.isoformat() if i.connected_at else None,
                "last_synced_at": i.last_synced_at.isoformat() if i.last_synced_at else None,
            }
            for i in integrations
        ],
        "count": len(integrations),
    }


async def _get_integration_status(integration_type: str, tenant_id: str, db: Prisma) -> dict:
    if not integration_type:
        return {"error": "integration_type is required"}
    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": integration_type}
    )
    if not integration:
        return {"error": f"Integration '{integration_type}' not found"}
    return {
        "id": integration.id,
        "type": integration.type,
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
    }


# ---------------------------------------------------------------------------
# Action tools — audit log written BEFORE DB mutation
# ---------------------------------------------------------------------------

async def _approve_execution(
    approval_id: str, note: str, tenant_id: str, user_id: Optional[str], db: Prisma
) -> dict:
    if not approval_id:
        return {"error": "approval_id is required"}
    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": tenant_id, "status": "pending"}
    )
    if not approval:
        return {"error": f"Pending approval {approval_id} not found"}
    actor = f"clen/{user_id}" if user_id else "clen/unknown"
    await write_audit_log(
        tenant_id=tenant_id,
        actor=actor,
        action="approve_execution",
        reasoning_trace={"approval_id": approval_id, "note": note},
        model_version=CLEN_MODEL_VERSION,
        execution_id=approval.execution_id,
    )
    await db.approval.update(
        where={"id": approval_id},
        data={"status": "approved", "responded_at": datetime.now(UTC)},
    )
    return {"approved": True, "approval_id": approval_id}


async def _reject_execution(
    approval_id: str, reason: str, tenant_id: str, user_id: Optional[str], db: Prisma
) -> dict:
    if not approval_id:
        return {"error": "approval_id is required"}
    if not reason:
        return {"error": "reason is required for rejection"}
    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": tenant_id, "status": "pending"}
    )
    if not approval:
        return {"error": f"Pending approval {approval_id} not found"}
    actor = f"clen/{user_id}" if user_id else "clen/unknown"
    await write_audit_log(
        tenant_id=tenant_id,
        actor=actor,
        action="reject_execution",
        reasoning_trace={"approval_id": approval_id, "reason": reason},
        model_version=CLEN_MODEL_VERSION,
        execution_id=approval.execution_id,
    )
    await db.approval.update(
        where={"id": approval_id},
        data={"status": "rejected", "responded_at": datetime.now(UTC)},
    )
    return {"rejected": True, "approval_id": approval_id}


async def _pause_worker(
    worker_type: str, tenant_id: str, user_id: Optional[str], db: Prisma
) -> dict:
    if not worker_type:
        return {"error": "worker_type is required"}
    existing = await db.worker.find_first(where={"tenant_id": tenant_id, "type": worker_type})
    if not existing:
        return {"error": f"Worker type '{worker_type}' not found"}
    actor = f"clen/{user_id}" if user_id else "clen/unknown"
    await write_audit_log(
        tenant_id=tenant_id,
        actor=actor,
        action="pause_worker",
        reasoning_trace={"worker_type": worker_type},
        model_version=CLEN_MODEL_VERSION,
    )
    updated = await db.worker.update_many(
        where={"tenant_id": tenant_id, "type": worker_type},
        data={"status": "inactive"},
    )
    return {"paused": True, "worker_type": worker_type, "updated_count": updated}
