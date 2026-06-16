from datetime import datetime, UTC, timedelta
from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, EmailStr, field_validator

from app.core.db import get_db_dep
from app.core.security import RequireAuth, RequireOrgAuth, CurrentUser, extract_clerk_user_id, require_role
from app.core.responses import standard_response
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/organisations", tags=["organisations"])

INVITATION_TTL_HOURS = 72
VALID_INVITE_ROLES = ("ADMIN", "APPROVER", "VIEWER")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class OrgProvisionResponse(BaseModel):
    tenant_id: str
    clerk_org_id: str
    name: str
    created_at: datetime


class OrgProfileResponse(BaseModel):
    id: str
    name: str
    industry: Optional[str]
    size: Optional[str]
    domain: Optional[str]
    domain_matching: bool
    onboarding_complete: bool
    created_at: datetime


class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    domain: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class MemberResponse(BaseModel):
    id: str
    clerk_user_id: str
    email: str
    role: str
    joined_at: datetime
    is_self: bool = False


class MemberRoleUpdateRequest(BaseModel):
    role: Literal["admin", "approver", "viewer"]


class TransferOwnershipRequest(BaseModel):
    new_owner_id: str


class CreateInviteLinkRequest(BaseModel):
    role: Literal["admin", "approver", "viewer"] = "viewer"
    expires_in_hours: int = 168  # 7 days default

    @field_validator("expires_in_hours")
    @classmethod
    def valid_expiry(cls, v: int) -> int:
        if v not in (1, 24, 168, 720, 8760):
            raise ValueError("expires_in_hours must be 1, 24, 168, 720, or 8760")
        return v


class InviteLinkResponse(BaseModel):
    id: str
    token: str
    role: str
    created_at: datetime
    expires_at: datetime


class InvitationRequest(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "APPROVER", "VIEWER"]


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    invited_by: str
    created_at: datetime
    expires_at: datetime


class DomainSettingsRequest(BaseModel):
    domain_matching: bool


class ProvisionRequest(BaseModel):
    email: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def provision_org(
    body: ProvisionRequest,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Provision org on first signup. Idempotent.
    If org_id is present in JWT, links tenant to Clerk org.
    If not (Clerk Organizations disabled), provisions using user sub alone.
    Email is taken from request body (most reliable), falling back to JWT claims.
    """
    clerk_user_id = extract_clerk_user_id(payload)
    org_id: str = payload.get("org_id", "")
    email: str = body.email or payload.get("email", "") or payload.get("email_address", "")

    if org_id:
        existing = await db.tenant.find_unique(where={"clerk_org_id": org_id})
        if existing:
            logger.info("Org already provisioned", extra={"org_id": org_id})
            if email:
                await db.member.update_many(
                    where={"clerk_user_id": clerk_user_id, "email": ""},
                    data={"email": email},
                )
            return standard_response(
                data=OrgProvisionResponse(
                    tenant_id=existing.id,
                    clerk_org_id=org_id,
                    name=existing.name,
                    created_at=existing.created_at,
                ).model_dump()
            )
        async with db.tx() as tx:
            tenant = await tx.tenant.create(data={"name": "My Organisation", "clerk_org_id": org_id})
            await tx.member.create(
                data={"tenant_id": tenant.id, "clerk_user_id": clerk_user_id, "email": email, "role": "OWNER"}
            )
    else:
        # Clerk Organizations not configured — provision by user identity
        existing_member = await db.member.find_unique(where={"clerk_user_id": clerk_user_id})
        if existing_member:
            tenant = await db.tenant.find_unique(where={"id": existing_member.tenant_id})
            if tenant:
                logger.info("Org already provisioned (no-org flow)", extra={"tenant_id": tenant.id})
                if email and not existing_member.email:
                    await db.member.update(
                        where={"clerk_user_id": clerk_user_id},
                        data={"email": email},
                    )
                return standard_response(
                    data=OrgProvisionResponse(
                        tenant_id=tenant.id,
                        clerk_org_id=tenant.clerk_org_id or "",
                        name=tenant.name,
                        created_at=tenant.created_at,
                    ).model_dump()
                )
        async with db.tx() as tx:
            tenant = await tx.tenant.create(data={"name": "My Organisation"})
            await tx.member.create(
                data={"tenant_id": tenant.id, "clerk_user_id": clerk_user_id, "email": email, "role": "OWNER"}
            )

    logger.info("Org provisioned", extra={"tenant_id": tenant.id, "org_id": org_id or "(none)"})
    return standard_response(
        data=OrgProvisionResponse(
            tenant_id=tenant.id,
            clerk_org_id=tenant.clerk_org_id or "",
            name=tenant.name,
            created_at=tenant.created_at,
        ).model_dump()
    )


@router.get("/me")
async def get_org(current_user: RequireOrgAuth, db: Annotated[Prisma, Depends(get_db_dep)]):
    """Return org profile for the authenticated user's organisation."""
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    return standard_response(
        data=OrgProfileResponse(
            id=tenant.id,
            name=tenant.name,
            industry=tenant.industry,
            size=tenant.size,
            domain=tenant.domain,
            domain_matching=tenant.domain_matching,
            onboarding_complete=tenant.onboarding_complete,
            created_at=tenant.created_at,
        ).model_dump()
    )


@router.patch("/me")
async def update_org(
    body: OrgUpdateRequest,
    current_user: Annotated[CurrentUser, require_role("owner")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Update org profile. Owner only."""
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    tenant = await db.tenant.update(
        where={"id": current_user.tenant_id},
        data=update_data,
    )
    logger.info("Org updated", extra={"tenant_id": current_user.tenant_id, "fields": list(update_data.keys())})

    return standard_response(
        data=OrgProfileResponse(
            id=tenant.id,
            name=tenant.name,
            industry=tenant.industry,
            size=tenant.size,
            domain=tenant.domain,
            domain_matching=tenant.domain_matching,
            onboarding_complete=tenant.onboarding_complete,
            created_at=tenant.created_at,
        ).model_dump()
    )


@router.get("/me/members")
async def list_members(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all members of the current organisation."""
    members = await db.member.find_many(where={"tenant_id": current_user.tenant_id})
    return standard_response(
        data=[
            MemberResponse(
                id=m.id,
                clerk_user_id=m.clerk_user_id,
                email=m.email,
                role=(m.role if isinstance(m.role, str) else m.role.value).lower(),
                joined_at=m.joined_at,
                is_self=m.clerk_user_id == current_user.user_id,
            ).model_dump()
            for m in members
        ]
    )


@router.delete("/me/members/{member_id}", status_code=status.HTTP_200_OK)
async def remove_member(
    member_id: str,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Remove a member. Cannot remove self or the owner."""
    member = await db.member.find_first(
        where={"id": member_id, "tenant_id": current_user.tenant_id}
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.clerk_user_id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")

    if (member.role if isinstance(member.role, str) else member.role.value) == "OWNER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the organisation owner")

    await db.member.delete(where={"id": member_id})
    logger.info("Member removed", extra={"tenant_id": current_user.tenant_id, "member_id": member_id})
    return standard_response(data={"removed": member_id})


@router.patch("/me/members/{member_id}")
async def update_member_role(
    member_id: str,
    body: MemberRoleUpdateRequest,
    current_user: Annotated[CurrentUser, require_role("owner")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Update a member's role. Cannot change the owner's role. Owner only."""
    member = await db.member.find_first(
        where={"id": member_id, "tenant_id": current_user.tenant_id}
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if (member.role if isinstance(member.role, str) else member.role.value) == "OWNER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")

    updated = await db.member.update(
        where={"id": member_id},
        data={"role": body.role.upper()},
    )
    logger.info("Member role updated", extra={"tenant_id": current_user.tenant_id, "member_id": member_id, "role": body.role})
    return standard_response(
        data=MemberResponse(
            id=updated.id,
            clerk_user_id=updated.clerk_user_id,
            email=updated.email,
            role=(updated.role if isinstance(updated.role, str) else updated.role.value).lower(),
            joined_at=updated.joined_at,
            is_self=updated.clerk_user_id == current_user.user_id,
        ).model_dump()
    )


@router.post("/me/transfer-ownership", status_code=status.HTTP_200_OK)
async def transfer_ownership(
    body: TransferOwnershipRequest,
    current_user: Annotated[CurrentUser, require_role("owner")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Transfer ownership to another member. Current owner becomes admin. Owner only."""
    new_owner = await db.member.find_first(
        where={"id": body.new_owner_id, "tenant_id": current_user.tenant_id}
    )
    if not new_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if new_owner.clerk_user_id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already the owner")

    async with db.tx() as tx:
        await tx.member.update(
            where={"clerk_user_id": current_user.user_id},
            data={"role": "ADMIN"},
        )
        await tx.member.update(
            where={"id": body.new_owner_id},
            data={"role": "OWNER"},
        )

    logger.info(
        "Ownership transferred",
        extra={"tenant_id": current_user.tenant_id, "from": current_user.user_id, "to": body.new_owner_id},
    )
    return standard_response(data={"transferred": True})


@router.post("/me/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationRequest,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Create an invitation. Role cannot be OWNER. Email must not already be a member."""
    existing_member = await db.member.find_first(
        where={"tenant_id": current_user.tenant_id, "email": body.email}
    )
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already a member of the organisation",
        )

    existing_invite = await db.invitation.find_first(
        where={"tenant_id": current_user.tenant_id, "email": body.email, "status": "PENDING"}
    )
    if existing_invite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending invitation already exists for this email",
        )

    expires_at = datetime.now(UTC) + timedelta(hours=INVITATION_TTL_HOURS)
    invitation = await db.invitation.create(
        data={
            "tenant_id": current_user.tenant_id,
            "email": body.email,
            "role": body.role,
            "invited_by": current_user.user_id,
            "expires_at": expires_at,
        }
    )
    logger.info("Invitation created", extra={"tenant_id": current_user.tenant_id, "email": body.email})
    return standard_response(
        data=InvitationResponse(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role if isinstance(invitation.role, str) else invitation.role.value,
            status=invitation.status if isinstance(invitation.status, str) else invitation.status.value,
            invited_by=invitation.invited_by,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
        ).model_dump()
    )


@router.get("/me/invitations")
async def list_invitations(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all PENDING invitations for the organisation."""
    invitations = await db.invitation.find_many(
        where={"tenant_id": current_user.tenant_id, "status": "PENDING"}
    )
    return standard_response(
        data=[
            InvitationResponse(
                id=inv.id,
                email=inv.email,
                role=inv.role if isinstance(inv.role, str) else inv.role.value,
                status=inv.status if isinstance(inv.status, str) else inv.status.value,
                invited_by=inv.invited_by,
                created_at=inv.created_at,
                expires_at=inv.expires_at,
            ).model_dump()
            for inv in invitations
        ]
    )


@router.delete("/me/invitations/{inv_id}", status_code=status.HTTP_200_OK)
async def revoke_invitation(
    inv_id: str,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revoke a pending invitation."""
    invitation = await db.invitation.find_first(
        where={"id": inv_id, "tenant_id": current_user.tenant_id}
    )
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status.value != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is not in PENDING state")

    await db.invitation.update(where={"id": inv_id}, data={"status": "REVOKED"})
    logger.info("Invitation revoked", extra={"tenant_id": current_user.tenant_id, "inv_id": inv_id})
    return standard_response(data={"revoked": inv_id})


@router.post("/me/invite-links", status_code=status.HTTP_201_CREATED)
async def create_invite_link(
    body: CreateInviteLinkRequest,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Generate a shareable invite link for the organisation."""
    expires_at = datetime.now(UTC) + timedelta(hours=body.expires_in_hours)
    link = await db.invitelink.create(
        data={
            "tenant_id": current_user.tenant_id,
            "role": body.role.upper(),
            "created_by": current_user.user_id,
            "expires_at": expires_at,
        }
    )
    logger.info("Invite link created", extra={"tenant_id": current_user.tenant_id, "link_id": link.id})
    return standard_response(
        data=InviteLinkResponse(
            id=link.id,
            token=link.token,
            role=link.role if isinstance(link.role, str) else link.role.value,
            created_at=link.created_at,
            expires_at=link.expires_at,
        ).model_dump()
    )


@router.get("/me/invite-links")
async def list_invite_links(
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all active (non-expired) invite links for the organisation."""
    links = await db.invitelink.find_many(
        where={
            "tenant_id": current_user.tenant_id,
            "expires_at": {"gt": datetime.now(UTC)},
        },
        order={"created_at": "desc"},
    )
    return standard_response(
        data=[
            InviteLinkResponse(
                id=lnk.id,
                token=lnk.token,
                role=lnk.role if isinstance(lnk.role, str) else lnk.role.value,
                created_at=lnk.created_at,
                expires_at=lnk.expires_at,
            ).model_dump()
            for lnk in links
        ]
    )


@router.delete("/me/invite-links/{link_id}", status_code=status.HTTP_200_OK)
async def delete_invite_link(
    link_id: str,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Delete (revoke) an invite link."""
    link = await db.invitelink.find_first(
        where={"id": link_id, "tenant_id": current_user.tenant_id}
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite link not found")

    await db.invitelink.delete(where={"id": link_id})
    logger.info("Invite link deleted", extra={"tenant_id": current_user.tenant_id, "link_id": link_id})
    return standard_response(data={"deleted": link_id})


@router.get("/join/{token}")
async def get_invite_link_info(
    token: str,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Public — returns org name and role for the invite link. No auth required."""
    link = await db.invitelink.find_first(
        where={"token": token},
        include={"tenant": True},
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite link not found")
    expires = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite link has expired")
    return standard_response(data={
        "org_name": link.tenant.name,
        "role": (link.role if isinstance(link.role, str) else link.role.value).lower(),
        "expires_at": link.expires_at.isoformat(),
    })


@router.post("/join/{token}")
async def accept_invite_link(
    token: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Accept an invite link. Creates a Member for the authenticated user in the org."""
    clerk_user_id = extract_clerk_user_id(payload)
    email: str = payload.get("email", "") or payload.get("email_address", "")

    link = await db.invitelink.find_first(where={"token": token})
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite link not found")
    expires = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This invite link has expired")

    existing = await db.member.find_first(
        where={"tenant_id": link.tenant_id, "clerk_user_id": clerk_user_id}
    )
    if existing:
        return standard_response(data={
            "tenant_id": link.tenant_id,
            "role": (existing.role if isinstance(existing.role, str) else existing.role.value).lower(),
            "already_member": True,
        })

    member = await db.member.create(data={
        "tenant_id": link.tenant_id,
        "clerk_user_id": clerk_user_id,
        "email": email,
        "role": link.role if isinstance(link.role, str) else link.role.value,
    })
    logger.info(
        "Member joined via invite link",
        extra={"tenant_id": link.tenant_id, "member_id": member.id, "link_id": link.id},
    )
    return standard_response(data={
        "tenant_id": link.tenant_id,
        "role": (member.role if isinstance(member.role, str) else member.role.value).lower(),
        "already_member": False,
    })


@router.patch("/me/settings")
async def update_domain_settings(
    body: DomainSettingsRequest,
    current_user: Annotated[CurrentUser, require_role("owner")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Toggle domain matching setting. Owner only."""
    await db.tenant.update(
        where={"id": current_user.tenant_id},
        data={"domain_matching": body.domain_matching},
    )
    logger.info(
        "Domain matching updated",
        extra={"tenant_id": current_user.tenant_id, "domain_matching": body.domain_matching},
    )
    return standard_response(data={"domain_matching": body.domain_matching})
