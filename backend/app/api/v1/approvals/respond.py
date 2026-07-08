from datetime import datetime, UTC
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from prisma import Prisma
from pydantic import BaseModel

from app.core.approvals import resolve_approval
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
    Approve or reject a pending approval. Enforces expiry TTL - stale approvals are rejected.
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

    responder = await db.user.find_first(
        where={"clerk_user_id": clerk_user_id, "tenant_id": tenant_id}
    )

    # Shared resolution: updates the approval + execution, cascades to the linked journal
    # entry and document, and writes the audit log. Same path the expiry cron uses.
    await resolve_approval(
        db=db,
        approval=approval,
        action=body.action.value,
        actor=f"user:{clerk_user_id}",
        responder_id=responder.id if responder else None,
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
