from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Json, Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

logger = get_logger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])

VALID_TYPES = {
    "invoice_processing", "receipt_processing",
    "reconciliation", "expense_control", "collections",
    "fraud_detection", "treasury", "revenue_recognition",
    "credit_underwriting", "compliance",
    "document_intelligence", "spend_control", "ar_collections",
    "risk_compliance", "treasury_cash", "tax_compliance",
    "financial_reporting", "payment_run", "budgeting",
}
VALID_AUTONOMY_LEVELS = {"auto", "approve"}
VALID_STATUSES = {"active", "inactive"}


class DeployToolRequest(BaseModel):
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


class PatchToolRequest(BaseModel):
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


def _serialize_tool(w: Any) -> dict:
    return {
        "id": w.id,
        "type": w.type,
        "autonomy_level": w.autonomy_level,
        "status": w.status,
        "version": w.version,
        "config_json": w.config_json,
        "last_configured_by_email": w.last_configured_by_email,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def deploy_tool(
    body: DeployToolRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Deploy a new tool for the tenant."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.create(
        data={
            "tenant": {"connect": {"id": tenant_id}},
            "type": body.type,
            "autonomy_level": body.autonomy_level,
            "config_json": Json(body.config),
            "status": "active",
            "version": 1,
            "last_configured_by_email": current_user.email,
        }
    )

    logger.info(
        "tool_deployed",
        extra={"tool_id": tool.id, "type": tool.type, "tenant_id": tenant_id},
    )

    return standard_response(data=_serialize_tool(tool))


@router.get("")
async def list_tools(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all tools for the tenant."""
    tenant_id = current_user.tenant_id

    tools = await db.tool.find_many(
        where={"tenant_id": tenant_id},
        order={"type": "asc"},
    )

    return standard_response(
        data={"tools": [_serialize_tool(w) for w in tools]}
    )


@router.get("/{tool_id}")
async def get_tool(
    tool_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Get a single tool scoped to the tenant."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    return standard_response(data=_serialize_tool(tool))


@router.patch("/{tool_id}")
async def update_tool(
    tool_id: str,
    body: PatchToolRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Partially update a tool. Bumps version on any change."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    update_data: dict[str, Any] = {"version": tool.version + 1}
    if body.autonomy_level is not None:
        update_data["autonomy_level"] = body.autonomy_level
    if body.status is not None:
        update_data["status"] = body.status
    if body.config is not None:
        update_data["config_json"] = Json(body.config)
    if current_user.email:
        update_data["last_configured_by_email"] = current_user.email

    updated = await db.tool.update(
        where={"id": tool_id},
        data=update_data,
    )

    logger.info(
        "tool_updated",
        extra={
            "tool_id": tool_id,
            "tenant_id": tenant_id,
            "new_version": updated.version,
        },
    )

    return standard_response(data=_serialize_tool(updated))


@router.patch("/{tool_id}/pause")
async def pause_tool(
    tool_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Toggle a tool between active and inactive."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    new_status = "inactive" if tool.status == "active" else "active"
    updated = await db.tool.update(
        where={"id": tool_id},
        data={"status": new_status, "version": tool.version + 1},
    )

    logger.info("tool_toggled", extra={"tool_id": tool_id, "tenant_id": tenant_id, "status": new_status})
    return standard_response(data=_serialize_tool(updated))


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Permanently delete a tool and all associated executions."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    await db.tool.delete(where={"id": tool_id})

    logger.info("tool_deleted", extra={"tool_id": tool_id, "tenant_id": tenant_id})
