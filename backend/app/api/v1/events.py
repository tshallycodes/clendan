"""
POST /v1/events — single orchestrator entry point.
External triggers and partner systems submit financial events here.
The orchestrator classifies, routes to the right worker, applies policy, and audits.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.orchestrator.events import enqueue_orchestrator_event
from app.orchestrator.orchestrator import EVENT_TO_WORKER

logger = get_logger(__name__)
router = APIRouter(prefix="/events", tags=["events"])

_VALID_TYPES = frozenset(EVENT_TO_WORKER.keys())


class EventRequest(BaseModel):
    event_type: str
    payload: dict

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"Unknown event_type. Valid: {sorted(_VALID_TYPES)}")
        return v


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_event(
    body: EventRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Submit a financial event to the orchestrator.
    Idempotent via Idempotency-Key header — same key returns the existing execution.
    """
    # Idempotency check before creating anything
    existing = await db.execution.find_first(
        where={"tenant_id": current_user.tenant_id, "input_ref": idempotency_key}
    )
    if existing and existing.status != "failed":
        return standard_response(data={
            "execution_id": existing.id,
            "status": existing.status,
            "decision": existing.decision,
            "idempotent": True,
        })

    execution_id = await enqueue_orchestrator_event(
        tenant_id=current_user.tenant_id,
        event_type=body.event_type,
        payload=body.payload,
        idempotency_key=idempotency_key,
        db=db,
    )

    if execution_id is None:
        worker_type = EVENT_TO_WORKER[body.event_type]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No active '{worker_type.value}' worker deployed for your tenant. "
                "Deploy one via POST /v1/tools."
            ),
        )

    return standard_response(data={
        "execution_id": execution_id,
        "status": "queued",
        "decision": "pending",
        "idempotent": False,
    })
