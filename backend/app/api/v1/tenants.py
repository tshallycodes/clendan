from datetime import datetime
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator
from zoneinfo import ZoneInfoNotFoundError

from app.core.db import get_db_dep
from app.core.security import RequireOrgAuth
from app.core.responses import standard_response
from app.models.schemas import TenantResponse

router = APIRouter(tags=["tenants"])


class PatchTenantRequest(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 200:
            raise ValueError("name must be 200 characters or fewer")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Unknown timezone: {v}")
        return v


class MemberItem(BaseModel):
    id: str
    email: str
    role: str
    joined_at: Optional[datetime] = None


@router.get("/tenants/me")
async def get_my_tenant(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns authenticated user's tenant. Checks Member table first, falls back to User table."""
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    member = await db.member.find_unique(where={"clerk_user_id": current_user.user_id})
    if member:
        role = member.role.lower()
        email = member.email
        # Backfill empty email from JWT on next login
        if not email and current_user.email:
            await db.member.update(
                where={"clerk_user_id": current_user.user_id},
                data={"email": current_user.email},
            )
            email = current_user.email
    else:
        user = await db.user.find_unique(where={"clerk_user_id": current_user.user_id})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        role = user.role
        email = user.email

    return standard_response(
        data={
            "tenant": TenantResponse(**tenant.model_dump()).model_dump(),
            "user": {"email": email, "role": role},
        }
    )


@router.get("/tenants/me/members")
async def list_members(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns all members of the authenticated user's tenant. Scoped to tenant."""
    members = await db.member.find_many(where={"tenant_id": current_user.tenant_id})
    if members:
        # Backfill email for the current user's row if it was stored empty
        if current_user.email:
            for m in members:
                if m.clerk_user_id == current_user.user_id and not m.email:
                    await db.member.update(
                        where={"clerk_user_id": current_user.user_id},
                        data={"email": current_user.email},
                    )
                    m.email = current_user.email
                    break
        return standard_response(
            data={"members": [MemberItem(id=m.id, email=m.email, role=m.role.lower(), joined_at=m.joined_at).model_dump() for m in members]}
        )
    # Fallback: users created via legacy onboarding path
    users = await db.user.find_many(where={"tenant_id": current_user.tenant_id})
    return standard_response(
        data={"members": [MemberItem(id=u.id, email=u.email, role=u.role).model_dump() for u in users]}
    )


@router.patch("/tenants/me")
async def patch_my_tenant(
    body: PatchTenantRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Update the authenticated user's tenant. Supports: name, timezone."""
    patch: dict = {}
    if body.name is not None:
        patch["name"] = body.name
    if body.timezone is not None:
        patch["timezone"] = body.timezone
    if not patch:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nothing to update")

    updated_tenant = await db.tenant.update(
        where={"id": current_user.tenant_id},
        data=patch,
    )
    if not updated_tenant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant not found",
        )

    return standard_response(
        data=TenantResponse(**updated_tenant.model_dump()).model_dump()
    )
