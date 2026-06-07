from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.security import RequireOrgAuth, CurrentUser
from app.core.responses import standard_response
from app.models.schemas import TenantResponse, UserResponse

router = APIRouter(tags=["tenants"])


class PatchTenantRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 200:
            raise ValueError("name must be 200 characters or fewer")
        return v


@router.get("/tenants/me")
async def get_my_tenant(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns authenticated user's tenant. Requires completed onboarding."""
    user = await db.user.find_unique(
        where={"clerk_user_id": current_user.user_id},
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found — complete onboarding first via POST /v1/onboarding",
        )
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tenant not found")

    return standard_response(
        data={
            "tenant": TenantResponse(**tenant.model_dump()).model_dump(),
            "user": UserResponse(**user.model_dump()).model_dump(),
        }
    )


@router.get("/tenants/me/members")
async def list_members(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns all users in the authenticated user's tenant. Scoped to tenant."""
    members = await db.user.find_many(where={"tenant_id": current_user.tenant_id})
    return standard_response(
        data={"members": [UserResponse(**m.model_dump()).model_dump() for m in members]}
    )


@router.patch("/tenants/me")
async def patch_my_tenant(
    body: PatchTenantRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Update the authenticated user's tenant. Currently supports: name."""
    updated_tenant = await db.tenant.update(
        where={"id": current_user.tenant_id},
        data={"name": body.name},
    )
    if not updated_tenant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant not found",
        )

    return standard_response(
        data=TenantResponse(**updated_tenant.model_dump()).model_dump()
    )
