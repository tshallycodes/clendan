import httpx
from typing import Annotated, Literal
from fastapi import Depends, HTTPException, Security, status
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
    org_id: str     # Clerk org ID — from JWT only, never from request
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
                detail="Organisation not provisioned — complete onboarding",
            )
        # Clerk JWTs don't include email by default — fall back to Member table
        if not email:
            member = await db.member.find_unique(where={"clerk_user_id": user_id})
            if member and member.email:
                email = member.email
    else:
        # Clerk Organizations not active — resolve tenant via Member table
        member = await db.member.find_unique(where={"clerk_user_id": user_id})
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organisation found — complete onboarding",
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
