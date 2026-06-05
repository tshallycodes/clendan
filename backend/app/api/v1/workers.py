from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from prisma import Json, Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireAuth, extract_clerk_user_id

logger = get_logger(__name__)
router = APIRouter(prefix="/workers", tags=["workers"])

VALID_TYPES = {
    "invoice_processing", "ai_accountant", "receipt_processing",
    "reconciliation", "expense_control", "collections",
    "fraud_detection", "treasury", "revenue_recognition",
    "credit_underwriting", "compliance",
}
VALID_AUTONOMY_LEVELS = {"auto", "approve", "suggest"}
VALID_STATUSES = {"active", "inactive"}


class DeployWorkerRequest(BaseModel):
    type: str
    autonomy_level: str = "approve"
    config: dict[str, Any] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of: {', '.join(sorted(VALID_TYPES))}")
        return v

    @field_validator("autonomy_level")
    @classmethod
    def validate_autonomy_level(cls, v: str) -> str:
        if v not in VALID_AUTONOMY_LEVELS:
            raise ValueError(
                f"autonomy_level must be one of: {', '.join(sorted(VALID_AUTONOMY_LEVELS))}"
            )
        return v


class PatchWorkerRequest(BaseModel):
    autonomy_level: str | None = None
    status: str | None = None
    config: dict[str, Any] | None = None

    @field_validator("autonomy_level")
    @classmethod
    def validate_autonomy_level(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_AUTONOMY_LEVELS:
            raise ValueError(
                f"autonomy_level must be one of: {', '.join(sorted(VALID_AUTONOMY_LEVELS))}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )
        return v


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


def _serialize_worker(w: Any) -> dict:
    return {
        "id": w.id,
        "type": w.type,
        "autonomy_level": w.autonomy_level,
        "status": w.status,
        "version": w.version,
        "config_json": w.config_json,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def deploy_worker(
    body: DeployWorkerRequest,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Deploy a new worker for the tenant."""
    tenant_id = await _get_tenant_id(payload, db)

    worker = await db.worker.create(
        data={
            "tenant": {"connect": {"id": tenant_id}},
            "type": body.type,
            "autonomy_level": body.autonomy_level,
            "config_json": Json(body.config),
            "status": "active",
            "version": 1,
        }
    )

    logger.info(
        "worker_deployed",
        extra={"worker_id": worker.id, "type": worker.type, "tenant_id": tenant_id},
    )

    return standard_response(data=_serialize_worker(worker))


@router.get("")
async def list_workers(
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all workers for the tenant."""
    tenant_id = await _get_tenant_id(payload, db)

    workers = await db.worker.find_many(
        where={"tenant_id": tenant_id},
        order={"type": "asc"},
    )

    return standard_response(
        data={"workers": [_serialize_worker(w) for w in workers]}
    )


@router.get("/{worker_id}")
async def get_worker(
    worker_id: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Get a single worker scoped to the tenant."""
    tenant_id = await _get_tenant_id(payload, db)

    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    return standard_response(data=_serialize_worker(worker))


@router.patch("/{worker_id}")
async def update_worker(
    worker_id: str,
    body: PatchWorkerRequest,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Partially update a worker. Bumps version on any change."""
    tenant_id = await _get_tenant_id(payload, db)

    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    update_data: dict[str, Any] = {"version": worker.version + 1}
    if body.autonomy_level is not None:
        update_data["autonomy_level"] = body.autonomy_level
    if body.status is not None:
        update_data["status"] = body.status
    if body.config is not None:
        update_data["config_json"] = Json(body.config)

    updated = await db.worker.update(
        where={"id": worker_id},
        data=update_data,
    )

    logger.info(
        "worker_updated",
        extra={
            "worker_id": worker_id,
            "tenant_id": tenant_id,
            "new_version": updated.version,
        },
    )

    return standard_response(data=_serialize_worker(updated))


@router.patch("/{worker_id}/pause")
async def pause_worker(
    worker_id: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Toggle a worker between active and inactive."""
    tenant_id = await _get_tenant_id(payload, db)

    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    new_status = "inactive" if worker.status == "active" else "active"
    updated = await db.worker.update(
        where={"id": worker_id},
        data={"status": new_status, "version": worker.version + 1},
    )

    logger.info("worker_toggled", extra={"worker_id": worker_id, "tenant_id": tenant_id, "status": new_status})
    return standard_response(data=_serialize_worker(updated))


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_worker(
    worker_id: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Permanently delete a worker and all associated executions."""
    tenant_id = await _get_tenant_id(payload, db)

    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    await db.worker.delete(where={"id": worker_id})

    logger.info("worker_deleted", extra={"worker_id": worker_id, "tenant_id": tenant_id})
