from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireAuth, extract_clerk_user_id

logger = get_logger(__name__)
router = APIRouter(prefix="/decisions", tags=["decisions"])


async def _get_tenant_id(payload: dict, db: Prisma) -> str:
    user = await db.user.find_unique(
        where={"clerk_user_id": extract_clerk_user_id(payload)}
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complete onboarding first",
        )
    return user.tenant_id


@router.get("/{execution_id}/explain")
async def explain_decision(
    execution_id: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Return full explainability data for an execution: execution details plus
    the ordered reasoning trace from every associated audit log entry.
    Scoped to tenant — 404 if execution does not belong to the authenticated tenant.
    """
    tenant_id = await _get_tenant_id(payload, db)

    execution = await db.execution.find_first(
        where={"id": execution_id, "tenant_id": tenant_id}
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    audit_entries = await db.auditlog.find_many(
        where={"execution_id": execution_id, "tenant_id": tenant_id},
        order={"created_at": "asc"},
    )

    return standard_response(
        data={
            "execution": {
                "id": execution.id,
                "worker_id": execution.worker_id,
                "decision": execution.decision,
                "confidence": execution.confidence,
                "status": execution.status,
                "created_at": execution.created_at.isoformat(),
            },
            "reasoning_traces": [
                {
                    "audit_id": entry.id,
                    "actor": entry.actor,
                    "action": entry.action,
                    "model_version": entry.model_version,
                    "created_at": entry.created_at.isoformat(),
                    "reasoning_trace_json": entry.reasoning_trace_json,
                }
                for entry in audit_entries
            ],
        }
    )
