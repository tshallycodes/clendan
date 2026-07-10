"""Firm / portfolio routes — the accounting / fractional-CFO firm layer (the ICP).

A firm operates a portfolio of client tenants, each on their own QB/Xero + banks. A firm
member may act as any client tenant whose Tenant.firm_id belongs to one of their firms. Every
endpoint here is firm/tenant-scoped and authorised through app.core.security.authorise_client_access,
so a member can only ever reach client tenants under their own firm. Additive and backward
compatible: a non-firm user simply has no firms, so /firms/clients returns an empty portfolio.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from prisma import Prisma
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import (
    RequireOrgAuth,
    authorise_client_access,
    get_member_firm_ids,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/firms", tags=["firms"])

# Version stamped onto the act-as audit entry (agent decisions log the version used).
_FIRM_LAYER_VERSION = "firm-layer-v1"


class ClientHealth(BaseModel):
    tenant_id: str
    name: str
    firm_id: str | None
    pending_approvals: int
    connected_integrations: int


class ActAsContext(BaseModel):
    tenant_id: str
    name: str
    firm_id: str


@router.get("/clients")
async def list_clients(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List client tenants under the caller's firm(s) with lightweight health.

    Scoped to the caller's own firms only — cross-firm tenants are never reachable. Non-firm
    users have no firms and receive an empty portfolio (the switcher / page degrade gracefully).
    """
    firm_ids = await get_member_firm_ids(db, current_user.user_id)
    if not firm_ids:
        return standard_response(data={"clients": []})

    tenants = await db.tenant.find_many(
        where={"firm_id": {"in": firm_ids}},
        order={"name": "asc"},
    )

    clients: list[dict] = []
    for t in tenants:
        pending = await db.approval.count(
            where={"tenant_id": t.id, "status": "pending"}
        )
        connected = await db.integration.count(
            where={"tenant_id": t.id, "status": "connected"}
        )
        clients.append(
            ClientHealth(
                tenant_id=t.id,
                name=t.name,
                firm_id=t.firm_id,
                pending_approvals=pending,
                connected_integrations=connected,
            ).model_dump()
        )

    return standard_response(data={"clients": clients})


@router.post("/clients/{tenant_id}/act-as")
async def act_as_client(
    tenant_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Verify firm membership for the target client tenant and return the scoped context.

    Denies with 403 if the caller is not a member of the firm that owns the tenant. The switch
    is written to the client tenant's immutable audit log before returning — an act-as is an
    operator action and must be defensible.
    """
    target = await authorise_client_access(db, current_user.user_id, tenant_id)

    # Audit the act-as on the CLIENT tenant's trail (scoped per tenant). Audit write must
    # succeed before we return — write_audit_log raises if it cannot record the entry.
    await write_audit_log(
        tenant_id=target.id,
        actor=current_user.email or current_user.user_id,
        action="firm.act_as",
        reasoning_trace={
            "event": "firm_member_act_as_client",
            "firm_id": target.firm_id,
            "client_tenant_id": target.id,
            "client_name": target.name,
            "acting_member": current_user.user_id,
            "acting_from_tenant": current_user.tenant_id,
        },
        model_version=_FIRM_LAYER_VERSION,
    )

    logger.info(
        "firm_act_as",
        extra={
            "firm_id": target.firm_id,
            "client_tenant_id": target.id,
            "actor": current_user.user_id,
        },
    )

    return standard_response(
        data=ActAsContext(
            tenant_id=target.id,
            name=target.name,
            firm_id=target.firm_id,
        ).model_dump()
    )
