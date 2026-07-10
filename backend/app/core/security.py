import httpx
from typing import Annotated, Literal
from fastapi import Depends, Header, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import JWKError
from prisma import Prisma
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger

logger = get_logger(__name__)
_bearer = HTTPBearer()
_jwks_cache: dict | None = None

ROLE_MAP: dict[str, str] = {
    "org:owner": "owner",
    "org:admin": "admin",
    "org:approver": "approver",
    "org:viewer": "viewer",
    "org:member": "viewer",
}


async def _fetch_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    settings = get_settings()
    url = f"https://{settings.clerk_frontend_api}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache


async def _verify_jwt(token: str) -> dict:
    try:
        jwks = await _fetch_jwks()
        return jwt.decode(token, jwks, algorithms=["RS256"], options={"verify_aud": False})
    except (JWTError, JWKError, httpx.HTTPError) as exc:
        logger.error("Auth failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Verifies Clerk JWT. Returns raw decoded payload. Used by endpoints where org may not exist yet."""
    return await _verify_jwt(credentials.credentials)


def extract_clerk_user_id(payload: dict) -> str:
    """Extracts Clerk user ID from JWT sub claim. Kept for onboarding backward compat."""
    user_id = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing sub claim")
    return user_id


class CurrentUser(BaseModel):
    user_id: str    # Clerk user ID (sub claim)
    org_id: str     # Clerk org ID - from JWT only, never from request
    tenant_id: str  # Internal DB Tenant.id resolved from clerk_org_id
    email: str
    role: Literal["owner", "admin", "approver", "viewer"]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    db: Prisma = Depends(get_db_dep),
) -> CurrentUser:
    """
    Verifies JWT and resolves internal tenant_id.
    Primary: org_id from JWT → tenant via clerk_org_id (Clerk Organizations flow).
    Fallback: sub from JWT → tenant via Member.clerk_user_id (no-org flow).
    403 if no tenant can be resolved.
    """
    payload = await _verify_jwt(credentials.credentials)

    user_id = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing sub claim")

    email: str = payload.get("email", "") or payload.get("email_address", "")
    org_id: str = payload.get("org_id", "")

    if org_id:
        org_role = payload.get("org_role", "org:viewer")
        role: str = ROLE_MAP.get(org_role, "viewer")
        tenant = await db.tenant.find_unique(where={"clerk_org_id": org_id})
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organisation not provisioned - complete onboarding",
            )
        # Clerk JWTs don't include email by default - fall back to Member table
        if not email:
            member = await db.member.find_unique(where={"clerk_user_id": user_id})
            if member and member.email:
                email = member.email
    else:
        # Clerk Organizations not active - resolve tenant via Member table
        member = await db.member.find_unique(where={"clerk_user_id": user_id})
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organisation found - complete onboarding",
            )
        tenant = await db.tenant.find_unique(where={"id": member.tenant_id})
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organisation not found",
            )
        role = member.role.lower()
        if not email and member.email:
            email = member.email

    return CurrentUser(
        user_id=user_id,
        org_id=org_id,
        tenant_id=tenant.id,
        email=email,
        role=role,
    )


def require_role(*roles: str):
    """Returns a FastAPI Depends that enforces the caller has one of the required roles."""
    async def _check(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {' or '.join(roles)}",
            )
        return current_user
    return Depends(_check)


RequireAuth = Annotated[dict, Depends(require_auth)]
RequireOrgAuth = Annotated[CurrentUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Firm / portfolio layer — act-as-client resolution (additive, backward-compatible)
# ---------------------------------------------------------------------------
# An accounting / fractional-CFO firm (the ICP) operates a portfolio of client tenants,
# each on their own QB/Xero + banks. A firm member may "act as" any client tenant whose
# Tenant.firm_id belongs to one of the member's firms. Every act-as is authorised against
# firm membership (cross-firm access is impossible) and produces an auditable trail. Non-firm
# users never trigger any of this: with no client selector the caller keeps their own tenant,
# so existing RequireOrgAuth / CurrentUser flows behave exactly as before.

CLIENT_HEADER = "X-Clendan-Client"


class ActiveContext(BaseModel):
    """Resolved request scope. For a normal user this is just their own tenant; for a firm
    member acting as a client, tenant_id is the client tenant and acting_as is True. The
    caller's identity and role (user) never change — only the tenant we scope queries to."""
    user: CurrentUser
    tenant_id: str
    firm_id: str | None = None
    acting_as: bool = False


async def get_member_firm_ids(db: Prisma, clerk_user_id: str) -> list[str]:
    """Firm IDs the caller belongs to via FirmMembership. Empty list for non-firm users.
    FirmMembership.member_id is the internal Member.id; the raw clerk_user_id is also accepted
    as a candidate so either seeding convention resolves correctly."""
    member = await db.member.find_unique(where={"clerk_user_id": clerk_user_id})
    candidates = [clerk_user_id]
    if member:
        candidates.append(member.id)
    memberships = await db.firmmembership.find_many(where={"member_id": {"in": candidates}})
    return [m.firm_id for m in memberships]


async def authorise_client_access(db: Prisma, clerk_user_id: str, target_tenant_id: str):
    """Single authorisation gate for every firm act-as. Returns the target client Tenant if the
    caller belongs to the firm that owns it; raises 403 otherwise. A member can ONLY reach client
    tenants under their own firm — the target's firm_id must be one of the caller's own firms."""
    firm_ids = await get_member_firm_ids(db, clerk_user_id)
    if not firm_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to act as this client",
        )
    target = await db.tenant.find_unique(where={"id": target_tenant_id})
    if not target or target.firm_id is None or target.firm_id not in firm_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to act as this client",
        )
    return target


async def resolve_active_context(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Prisma, Depends(get_db_dep)],
    x_clendan_client: Annotated[str | None, Header(alias=CLIENT_HEADER)] = None,
    client: Annotated[str | None, Query()] = None,
) -> ActiveContext:
    """Resolve the ACTIVE tenant for a request.

    No client selector -> the caller's own tenant (existing behaviour, unchanged for everyone).
    Selector present (X-Clendan-Client header or ?client= query) -> the caller must be a firm
    member of the firm that owns that client tenant, else 403. Every resolved act-as is logged
    with the request trace id for an auditable trail. Apply this dependency to any route the
    client switcher must scope; routes that don't use it keep their own-tenant behaviour."""
    selector = (x_clendan_client or client or "").strip()
    if not selector or selector == current_user.tenant_id:
        return ActiveContext(user=current_user, tenant_id=current_user.tenant_id)
    target = await authorise_client_access(db, current_user.user_id, selector)
    logger.info(
        "firm_act_as_resolved",
        extra={
            "actor": current_user.user_id,
            "firm_id": target.firm_id,
            "client_tenant_id": target.id,
        },
    )
    return ActiveContext(
        user=current_user,
        tenant_id=target.id,
        firm_id=target.firm_id,
        acting_as=True,
    )


RequireActiveContext = Annotated[ActiveContext, Depends(resolve_active_context)]
