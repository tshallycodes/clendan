from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.security import RequireAuth, extract_clerk_user_id
from app.core.responses import standard_response
from app.models.schemas import OnboardingRequest, OnboardingResponse, TenantResponse, UserResponse

router = APIRouter(tags=["onboarding"])


@router.post("/onboarding")
async def onboard(
    body: OnboardingRequest,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Create tenant + user on first sign-in. Idempotent — safe to call multiple times."""
    clerk_user_id = extract_clerk_user_id(payload)
    email = payload.get("email", "") or payload.get("email_address", "")

    existing = await db.user.find_unique(where={"clerk_user_id": clerk_user_id})
    if existing:
        tenant = await db.tenant.find_unique(where={"id": existing.tenant_id})
        if not tenant:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tenant not found")
        return standard_response(
            data=OnboardingResponse(
                tenant=TenantResponse(**tenant.model_dump()),
                user=UserResponse(**existing.model_dump()),
            ).model_dump()
        )

    async with db.tx() as tx:
        tenant = await tx.tenant.create(data={"name": body.tenant_name})
        user = await tx.user.create(
            data={
                "tenant_id": tenant.id,
                "clerk_user_id": clerk_user_id,
                "email": email,
                "role": "owner",
            }
        )

    return standard_response(
        data=OnboardingResponse(
            tenant=TenantResponse(**tenant.model_dump()),
            user=UserResponse(**user.model_dump()),
        ).model_dump()
    )
