from datetime import datetime, UTC
from enum import Enum

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response

_logger = get_logger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class RespondRequest(BaseModel):
    action: ApprovalAction
    responder_id: str


@router.post("/{approval_id}/respond")
async def respond_to_approval(
    approval_id: str = Path(...),
    body: RespondRequest = ...,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
):
    """
    Approve or reject a pending approval. Enforces expiry TTL — stale approvals are rejected.
    Scoped to tenant: only approvals belonging to the requesting tenant are accessible.
    """
    db = get_db()

    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": x_tenant_id}
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

    # Update approval record
    updated_approval = await db.approval.update(
        where={"id": approval_id},
        data={
            "status": new_status,
            "responded_at": now,
            "responder_id": body.responder_id,
        },
    )

    # Update execution decision
    await db.execution.update(
        where={"id": approval.execution_id},
        data={"decision": new_decision},
    )

    # If approved: trigger mock accounting write
    if body.action == ApprovalAction.APPROVE:
        _logger.info(
            "mock_accounting_write_on_approval",
            extra={
                "tenant_id": x_tenant_id,
                "approval_id": approval_id,
                "execution_id": approval.execution_id,
            },
        )

    # Audit log — must succeed for operation to complete
    await write_audit_log(
        tenant_id=x_tenant_id,
        actor=f"user:{body.responder_id}",
        action=f"approval_{new_status}",
        reasoning_trace={
            "approval_id": approval_id,
            "execution_id": approval.execution_id,
            "action": body.action,
            "responder_id": body.responder_id,
        },
        model_version="human",
        execution_id=approval.execution_id,
    )

    _logger.info(
        "approval_responded",
        extra={
            "approval_id": approval_id,
            "action": body.action,
            "tenant_id": x_tenant_id,
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
