from datetime import datetime, UTC, timedelta
from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, EmailStr, field_validator

from app.core.db import get_db_dep
from app.core.security import RequireAuth, RequireOrgAuth, CurrentUser, extract_clerk_user_id, require_role
from app.core.responses import standard_response
from app.core.logging import get_logger
from app.models.schemas import OnboardingRequest, OnboardingResponse, TenantResponse, UserResponse

logger = get_logger(__name__)
router = APIRouter(tags=["onboarding"])

INVITATION_TTL_HOURS = 72
MAX_BATCH_INVITATIONS = 10


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class OnboardingStatusResponse(BaseModel):
    onboarding_complete: bool
    org_provisioned: bool


class OrgDetailsRequest(BaseModel):
    name: str
    industry: Optional[str] = None
    size: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class InviteEntry(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "APPROVER", "VIEWER"]


class InviteTeamRequest(BaseModel):
    invitations: list[InviteEntry]

    @field_validator("invitations")
    @classmethod
    def check_max(cls, v: list[InviteEntry]) -> list[InviteEntry]:
        if len(v) > MAX_BATCH_INVITATIONS:
            raise ValueError(f"Maximum {MAX_BATCH_INVITATIONS} invitations per request")
        if not v:
            raise ValueError("invitations list must not be empty")
        return v


class InviteTeamResponse(BaseModel):
    created: int
    skipped: int


# ---------------------------------------------------------------------------
# Existing endpoint — preserved for backward compat
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# New onboarding endpoints
# ---------------------------------------------------------------------------

@router.get("/onboarding/status")
async def get_onboarding_status(
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Return onboarding completion flags. Uses plain user auth so it works without an active Clerk org in the JWT."""
    clerk_user_id = extract_clerk_user_id(payload)

    member = await db.member.find_unique(where={"clerk_user_id": clerk_user_id})
    if not member:
        return standard_response(
            data=OnboardingStatusResponse(onboarding_complete=False, org_provisioned=False).model_dump()
        )

    tenant = await db.tenant.find_unique(where={"id": member.tenant_id})
    if not tenant:
        return standard_response(
            data=OnboardingStatusResponse(onboarding_complete=False, org_provisioned=False).model_dump()
        )

    return standard_response(
        data=OnboardingStatusResponse(
            onboarding_complete=tenant.onboarding_complete,
            org_provisioned=tenant.clerk_org_id is not None,
        ).model_dump()
    )


@router.post("/onboarding/organisation")
async def save_org_details(
    body: OrgDetailsRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Save company details to the Tenant record."""
    update_data: dict = {k: v for k, v in body.model_dump().items() if v is not None}

    tenant = await db.tenant.update(
        where={"id": current_user.tenant_id},
        data=update_data,
    )
    logger.info("Org details saved", extra={"tenant_id": current_user.tenant_id})
    return standard_response(data={"id": tenant.id, "name": tenant.name})


@router.post("/onboarding/invite-team")
async def invite_team(
    body: InviteTeamRequest,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Batch-create invitations during onboarding. Skips duplicates without failing."""
    expires_at = datetime.now(UTC) + timedelta(hours=INVITATION_TTL_HOURS)
    created = 0
    skipped = 0

    for entry in body.invitations:
        already_member = await db.member.find_first(
            where={"tenant_id": current_user.tenant_id, "email": entry.email}
        )
        if already_member:
            skipped += 1
            continue
        pending_invite = await db.invitation.find_first(
            where={"tenant_id": current_user.tenant_id, "email": entry.email, "status": "PENDING"}
        )
        if pending_invite:
            skipped += 1
            continue

        await db.invitation.create(
            data={
                "tenant_id": current_user.tenant_id,
                "email": entry.email,
                "role": entry.role,
                "invited_by": current_user.user_id,
                "expires_at": expires_at,
            }
        )
        created += 1

    logger.info("Batch invitations processed", extra={"tenant_id": current_user.tenant_id, "created": created, "skipped": skipped})
    return standard_response(data=InviteTeamResponse(created=created, skipped=skipped).model_dump())


@router.post("/onboarding/complete")
async def complete_onboarding(
    current_user: Annotated[CurrentUser, require_role("owner")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Mark onboarding as complete. Owner only."""
    await db.tenant.update(
        where={"id": current_user.tenant_id},
        data={"onboarding_complete": True},
    )
    logger.info("Onboarding complete", extra={"tenant_id": current_user.tenant_id})
    return standard_response(data={"onboarding_complete": True})
