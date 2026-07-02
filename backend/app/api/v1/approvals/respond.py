from datetime import datetime, UTC
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from prisma import Prisma
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

_logger = get_logger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class RespondRequest(BaseModel):
    action: ApprovalAction


@router.post("/{approval_id}/respond")
async def respond_to_approval(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    approval_id: str = Path(...),
    body: RespondRequest = ...,
):
    """
    Approve or reject a pending approval. Enforces expiry TTL — stale approvals are rejected.
    Scoped to tenant via JWT: only approvals belonging to the authenticated user's tenant are accessible.
    Cascades status to linked journal entries when applicable.
    """
    tenant_id = current_user.tenant_id
    clerk_user_id = current_user.user_id

    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": tenant_id}
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval is already '{approval.status}' and cannot be acted on",
        )

    now = datetime.now(UTC)
    if approval.expires_at.replace(tzinfo=UTC) < now:
        raise HTTPException(
            status_code=410,
            detail="Approval has expired and can no longer be acted on",
        )

    new_status = "approved" if body.action == ApprovalAction.APPROVE else "rejected"
    new_decision = "approved" if body.action == ApprovalAction.APPROVE else "rejected"

    responder = await db.user.find_first(
        where={"clerk_user_id": clerk_user_id, "tenant_id": tenant_id}
    )

    approval_update: dict = {"status": new_status, "responded_at": now}
    if responder:
        approval_update["responder_id"] = responder.id

    # Update approval record
    await db.approval.update(where={"id": approval_id}, data=approval_update)  # type: ignore[arg-type]

    # Update execution decision
    execution = await db.execution.find_unique(where={"id": approval.execution_id})
    await db.execution.update(
        where={"id": approval.execution_id},
        data={"decision": new_decision},
    )

    # Cascade to journal entry if this approval is linked to one
    if execution and execution.input_ref and execution.input_ref.startswith("journal_entry:"):
        parts = execution.input_ref.split(":")
        if len(parts) >= 2:
            je_id = parts[1]
            je_new_status = "approved" if body.action == ApprovalAction.APPROVE else "rejected"
            await db.journalentry.update_many(
                where={"id": je_id, "tenant_id": tenant_id, "status": "pending_approval"},
                data={"status": je_new_status},
            )
            _logger.info(
                "journal_entry_approval_cascaded",
                extra={
                    "journal_entry_id": je_id,
                    "new_status": je_new_status,
                    "approval_id": approval_id,
                    "tenant_id": tenant_id,
                },
            )

    # Cascade decision to document so the Documents tab reflects the outcome
    if body.action == ApprovalAction.REJECT:
        await db.document.update_many(
            where={"execution_id": approval.execution_id, "tenant_id": tenant_id},
            data={"decision": "blocked"},
        )
    else:
        await db.document.update_many(
            where={"execution_id": approval.execution_id, "tenant_id": tenant_id},
            data={"decision": "auto_approved"},
        )

    # Audit log — must succeed for operation to complete
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"user:{clerk_user_id}",
        action=f"approval_{new_status}",
        reasoning_trace={
            "approval_id": approval_id,
            "execution_id": approval.execution_id,
            "action": body.action,
        },
        model_version="human",
        execution_id=approval.execution_id,
    )

    _logger.info(
        "approval_responded",
        extra={
            "approval_id": approval_id,
            "action": body.action,
            "tenant_id": tenant_id,
        },
    )

    return standard_response(
        data={
            "approval_id": approval_id,
            "status": new_status,
            "execution_id": approval.execution_id,
            "responded_at": now.isoformat(),
        }
    )
