"""Workflow connection routes - read and toggle the auto-handoff between tools.

A connection is the edge between two consecutive tools in a workflow. Enabled means
the upstream tool auto-advances to the downstream one on a successful run. A missing
row means enabled (default on). Only known edges (see WORKFLOW_EDGES) are accepted.
"""
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


class ConnectionPatch(BaseModel):
    from_type: str
    to_type: str
    enabled: bool


def _is_known_edge(from_type: str, to_type: str) -> bool:
    edge = WORKFLOW_EDGES.get(from_type)
    return edge is not None and edge[0] == to_type


@router.get("/connections")
async def list_connections(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns every workflow edge with its enabled state (default on when unset)."""
    rows = await db.workflowconnection.find_many(where={"tenant_id": current_user.tenant_id})
    enabled_by_edge = {(r.from_type, r.to_type): r.enabled for r in rows}

    connections = [
        {
            "from_type": from_type,
            "to_type": to_type,
            "enabled": enabled_by_edge.get((from_type, to_type), True),
        }
        for from_type, (to_type, _event) in WORKFLOW_EDGES.items()
    ]
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
