"""
Generic integration routes for all non-dedicated integrations.

OAuth (redirect flow):
    sage, wave, wise, dynamics365, dropbox, onedrive

API key (live validation before store):
    nordigen  - Secret ID + Secret Key (GoCardless for Banks)
    adyen     - API Key + environment

Stored credentials (validated on first sync):
    netsuite, sap, sage-intacct
"""
import secrets
import time
import urllib.parse
from datetime import datetime, UTC
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.integrations.encryption import encrypt_credentials
from app.integrations.oauth_registry import OAUTH_REGISTRY

logger = get_logger(__name__)
router = APIRouter(tags=["integrations"])

APIKEY_SLUGS: frozenset[str] = frozenset({"nordigen", "adyen"})
CREDENTIALS_SLUGS: frozenset[str] = frozenset({"netsuite", "sap", "sage-intacct"})
OAUTH_SLUGS: frozenset[str] = frozenset(OAUTH_REGISTRY.keys())
ALL_GENERIC_SLUGS: frozenset[str] = OAUTH_SLUGS | APIKEY_SLUGS | CREDENTIALS_SLUGS


def _require_slug(slug: str, allowed: frozenset[str]) -> None:
    if slug not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Integration '{slug}' not found")


def _redirect_uri(slug: str) -> str:
    return f"{get_settings().backend_base_url}/v1/integrations/{slug}/callback"


# ---------------------------------------------------------------------------
# OAuth - initiate
# ---------------------------------------------------------------------------

@router.get("/integrations/{slug}/connect")
async def generic_oauth_connect(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    _require_slug(slug, OAUTH_SLUGS)
    cfg = OAUTH_REGISTRY[slug]
    settings = get_settings()

    client_id = getattr(settings, cfg.client_id_attr, "")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{slug} OAuth credentials are not configured on this server",
        )

    state = f"{current_user.tenant_id}:{secrets.token_urlsafe(16)}"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": _redirect_uri(slug),
        "scope": cfg.scope,
        "state": state,
        **cfg.extra_auth_params,
    }
    auth_url = cfg.auth_url + "?" + urllib.parse.urlencode(params)
    return standard_response(data={"auth_url": auth_url})


# ---------------------------------------------------------------------------
# OAuth - callback
# ---------------------------------------------------------------------------

@router.get("/integrations/{slug}/callback")
async def generic_oauth_callback(
    slug: str,
    code: str = Query(...),
    state: str = Query(...),
    db: Prisma = Depends(get_db_dep),
):
    _require_slug(slug, OAUTH_SLUGS)

    parts = state.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    tenant_id = parts[0]

    tenant = await db.tenant.find_unique(where={"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    cfg = OAUTH_REGISTRY[slug]
    settings = get_settings()
    client_id = getattr(settings, cfg.client_id_attr, "")
    client_secret = getattr(settings, cfg.client_secret_attr, "")

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                cfg.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _redirect_uri(slug),
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as exc:
        logger.error("%s_token_exchange_failed tenant=%s error=%s", slug, tenant_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{slug} token exchange failed")

    expires_in = int(tokens.get("expires_in") or 3600)
    creds = {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }
    blob = encrypt_credentials(creds, tenant_id)

    existing = await db.integration.find_first(where={"tenant_id": tenant_id, "type": slug})
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={"encrypted_credentials": blob, "status": "syncing", "connected_at": datetime.now(UTC)},
        )
    else:
        integration = await db.integration.create(
            data={"tenant_id": tenant_id, "type": slug, "encrypted_credentials": blob,
                  "status": "syncing", "connected_at": datetime.now(UTC)},
        )

    logger.info("%s_connected tenant=%s integration=%s", slug, tenant_id, integration.id)
    frontend_url = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(url=f"{frontend_url}/dashboard/integrations?connected={slug}")


# ---------------------------------------------------------------------------
# API key / credentials - connect
# ---------------------------------------------------------------------------

@router.post("/integrations/{slug}/connect")
async def generic_credential_connect(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    credentials: dict[str, Any] = Body(...),
):
    _require_slug(slug, APIKEY_SLUGS | CREDENTIALS_SLUGS)

    if slug == "nordigen":
        await _validate_nordigen(credentials)
    elif slug == "adyen":
        await _validate_adyen(credentials)

    blob = encrypt_credentials({k: str(v) for k, v in credentials.items()}, current_user.tenant_id)

    existing = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": slug}
    )
    if existing:
        integration = await db.integration.update(
            where={"id": existing.id},
            data={"encrypted_credentials": blob, "status": "syncing", "connected_at": datetime.now(UTC)},
        )
    else:
        integration = await db.integration.create(
            data={"tenant_id": current_user.tenant_id, "type": slug, "encrypted_credentials": blob,
                  "status": "syncing", "connected_at": datetime.now(UTC)},
        )

    logger.info("%s_connected tenant=%s integration=%s", slug, current_user.tenant_id, integration.id)
    return standard_response(data={"status": "syncing", "integration_id": integration.id})


async def _validate_nordigen(credentials: dict) -> None:
    secret_id = credentials.get("secret_id", "")
    secret_key = credentials.get("secret_key", "")
    if not secret_id or not secret_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="secret_id and secret_key are required")
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(
                "https://bankaccountdata.gocardless.com/api/v2/token/new/",
                json={"secret_id": secret_id, "secret_key": secret_key},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Nordigen credentials")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Nordigen validation failed")
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Nordigen validation failed")


async def _validate_adyen(credentials: dict) -> None:
    api_key = credentials.get("api_key", "")
    environment = credentials.get("environment", "test")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="api_key is required")
    base = (
        "https://management-test.adyen.com"
        if environment == "test"
        else "https://management-live.adyen.com"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(
                f"{base}/v3/me",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Adyen API key")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Adyen validation failed")
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Adyen validation failed")


# ---------------------------------------------------------------------------
# Common: status / sync / disconnect
# ---------------------------------------------------------------------------

@router.get("/integrations/{slug}/status")
async def generic_status(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    _require_slug(slug, ALL_GENERIC_SLUGS)
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": slug}
    )
    if not integration:
        return standard_response(data={"status": "not_connected"})
    return standard_response(data={
        "status": integration.status,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
        "last_synced_at": integration.last_synced_at.isoformat() if integration.last_synced_at else None,
        "integration_id": integration.id,
        "summary": integration.sync_metadata,
    })


@router.post("/integrations/{slug}/sync")
async def generic_sync(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    _require_slug(slug, ALL_GENERIC_SLUGS)
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": slug}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {slug} connection found")
    if integration.status not in ("connected", "syncing", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot sync - integration status is '{integration.status}'",
        )
    await db.integration.update(where={"id": integration.id}, data={"status": "syncing"})
    return standard_response(data={"status": "sync_enqueued", "integration_id": integration.id})


@router.delete("/integrations/{slug}/disconnect")
async def generic_disconnect(
    slug: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    _require_slug(slug, ALL_GENERIC_SLUGS)
    integration = await db.integration.find_first(
        where={"tenant_id": current_user.tenant_id, "type": slug, "status": {"not": "disconnected"}}
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {slug} connection found")
    await db.integration.update(
        where={"id": integration.id},
        data={"status": "disconnected", "encrypted_credentials": "{}"},
    )
    logger.info("%s_disconnected tenant=%s integration=%s", slug, current_user.tenant_id, integration.id)
    return standard_response(data={"status": "disconnected"})
