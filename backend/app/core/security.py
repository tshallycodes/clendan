import httpx
from typing import Annotated
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import JWKError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_bearer = HTTPBearer()
_jwks_cache: dict | None = None


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


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Verifies Clerk JWT server-side. Returns decoded payload."""
    token = credentials.credentials
    try:
        jwks = await _fetch_jwks()
        payload: dict = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except (JWTError, JWKError, httpx.HTTPError) as exc:
        logger.error("Auth failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_clerk_user_id(payload: dict) -> str:
    """Extracts Clerk user ID from JWT payload sub claim."""
    user_id = payload.get("sub", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing sub claim",
        )
    return user_id


RequireAuth = Annotated[dict, Depends(require_auth)]
