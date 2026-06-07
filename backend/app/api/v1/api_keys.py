"""
API key management endpoints.

Keys are generated as `ck_live_` + 32 hex chars.
Only the SHA-256 hash is stored — the full key is returned once on creation.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth, CurrentUser

logger = get_logger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])

KEY_PREFIX_LEN = 12


class CreateApiKeyRequest(BaseModel):
    name: str
    expires_at: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    key: str  # full key — returned once only
    created_at: datetime
    expires_at: Optional[datetime]


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    key_prefix: str
    status: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]


class ApiKeyRevokedResponse(BaseModel):
    id: str
    status: str


def _generate_key() -> str:
    """Generate a new API key: ck_live_ + 32 hex chars."""
    return "ck_live_" + secrets.token_hex(16)


def _hash_key(key: str) -> str:
    """SHA-256 hex digest of the full key."""
    return hashlib.sha256(key.encode()).hexdigest()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Create a new API key for the tenant. The full key is returned once and never retrievable again."""
    tenant_id = current_user.tenant_id

    full_key = _generate_key()
    key_prefix = full_key[:KEY_PREFIX_LEN]
    key_hash = _hash_key(full_key)

    create_data: dict = {
        "tenant_id": tenant_id,
        "name": body.name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "status": "active",
    }
    if body.expires_at is not None:
        create_data["expires_at"] = body.expires_at

    api_key = await db.apikey.create(data=create_data)

    logger.info(
        "api_key_created",
        extra={"api_key_id": api_key.id, "tenant_id": tenant_id},
    )

    return standard_response(
        data=ApiKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            key=full_key,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
        ).model_dump()
    )


@router.get("")
async def list_api_keys(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all API keys for the tenant. Never returns key_hash or the full key."""
    tenant_id = current_user.tenant_id

    keys = await db.apikey.find_many(
        where={"tenant_id": tenant_id},
        order={"created_at": "desc"},
    )

    return standard_response(
        data={
            "api_keys": [
                ApiKeyListItem(
                    id=k.id,
                    name=k.name,
                    key_prefix=k.key_prefix,
                    status=k.status,
                    created_at=k.created_at,
                    last_used_at=k.last_used_at,
                    expires_at=k.expires_at,
                ).model_dump()
                for k in keys
            ]
        }
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Revoke an API key. Sets status=revoked — does not delete the row."""
    tenant_id = current_user.tenant_id

    api_key = await db.apikey.find_first(
        where={"id": key_id, "tenant_id": tenant_id}
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    updated = await db.apikey.update(
        where={"id": key_id},
        data={"status": "revoked"},
    )

    logger.info(
        "api_key_revoked",
        extra={"api_key_id": key_id, "tenant_id": tenant_id},
    )

    return standard_response(
        data=ApiKeyRevokedResponse(id=updated.id, status=updated.status).model_dump()
    )
