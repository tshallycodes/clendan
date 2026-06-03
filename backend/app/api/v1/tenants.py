from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.security import RequireAuth, extract_clerk_user_id
from app.core.responses import standard_response
from app.models.schemas import TenantResponse, UserResponse

router = APIRouter(tags=["tenants"])


@router.get("/tenants/me")
async def get_my_tenant(
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns authenticated user's tenant. Requires completed onboarding."""
    clerk_user_id = extract_clerk_user_id(payload)
    user = await db.user.find_unique(
        where={"clerk_user_id": clerk_user_id},
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found — complete onboarding first via POST /v1/onboarding",
        )
    tenant = await db.tenant.find_unique(where={"id": user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tenant not found")

    return standard_response(
        data={
            "tenant": TenantResponse(**tenant.model_dump()).model_dump(),
            "user": UserResponse(**user.model_dump()).model_dump(),
        }
    )
