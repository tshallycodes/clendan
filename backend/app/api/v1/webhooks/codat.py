"""
Codat webhook receiver.
Codat sends an Authorization header containing the configured API key or webhook secret.
Handles: DataSyncCompleted, DataSyncFailed, NewConnectionCreated.
"""
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.codat.sync import enqueue_codat_sync

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED_EVENTS = frozenset({
    "DataSyncCompleted",
    "DataSyncFailed",
    "NewConnectionCreated",
})


def _verify_authorization(authorization: str) -> bool:
    """
    Codat webhook auth: the Authorization header must match the configured
    dedicated webhook secret (preferred) or, failing that, the Codat API key.
    Comparison is constant-time to prevent timing attacks.
    """
    import hmac
    settings = get_settings()
    expected = settings.codat_webhook_secret or settings.codat_api_key
    if not expected:
        return False
    # Basic scheme: "Basic <token>" or raw token - handle both
    token = authorization.removeprefix("Basic ").strip()
    return hmac.compare_digest(expected.encode(), token.encode())


@router.post("/codat")
async def codat_webhook(
    request: Request,
    authorization: str = Header(..., alias="Authorization"),
):
    """
    Receives Codat event notifications.
    Authorization header verified before any processing.
    Unverified webhooks are rejected with 401.
    """
    settings = get_settings()

    if not (settings.codat_webhook_secret or settings.codat_api_key):
        _logger.error("codat_webhook_not_configured")
        raise HTTPException(status_code=503, detail="Codat webhook not configured")

    if not _verify_authorization(authorization):
        _logger.warning("codat_webhook_invalid_authorization")
        raise HTTPException(status_code=401, detail="Invalid webhook authorization")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = body.get("Type", body.get("eventType", ""))
    company_id = body.get("CompanyId", body.get("companyId", ""))

    _logger.info(
        "codat_webhook_received",
        extra={"event_type": event_type, "company_id": company_id},
    )

    if event_type not in _HANDLED_EVENTS:
        # Unknown event - acknowledge without processing
        return standard_response(data={"received": True, "processed": False})

    db = get_db()

    # Resolve integration from company_id stored in credentials
    integrations = await db.integration.find_many(
        where={"type": "codat", "status": {"not": "disconnected"}}
    )

    from app.integrations.encryption import decrypt_credentials
    integration = None
    for row in integrations:
        try:
            creds = decrypt_credentials(row.encrypted_credentials, row.tenant_id)
            if creds.get("company_id") == company_id:
                integration = row
                break
        except ValueError:
            continue

    if not integration and event_type != "NewConnectionCreated":
        _logger.warning(
            "codat_webhook_no_integration",
            extra={"event_type": event_type, "company_id": company_id},
        )
        return standard_response(data={"received": True, "processed": False})

    if event_type == "NewConnectionCreated":
        if integration:
            await db.integration.update(
                where={"id": integration.id},
                data={"status": "syncing"},
            )
            try:
                await enqueue_codat_sync(
                    integration_id=integration.id,
                    tenant_id=integration.tenant_id,
                )
            except Exception as exc:
                _logger.error(
                    "codat_webhook_enqueue_failed",
                    extra={"error": str(exc), "integration_id": integration.id},
                )
        _logger.info(
            "codat_new_connection_created",
            extra={"company_id": company_id},
        )

    elif event_type == "DataSyncCompleted":
        await db.integration.update(
            where={"id": integration.id},
            data={"status": "connected"},
        )
        await db.integrationsynclog.create(data={
            "tenant_id": integration.tenant_id,
            "integration_id": integration.id,
            "entity_type": "webhook",
            "status": "success",
            "records_synced": 0,
            "duration_ms": 0,
        })
        _logger.info(
            "codat_data_sync_completed",
            extra={"company_id": company_id, "integration_id": integration.id},
        )

    elif event_type == "DataSyncFailed":
        _logger.warning(
            "codat_data_sync_failed",
            extra={
                "company_id": company_id,
                "integration_id": integration.id,
                "error": body.get("data", {}).get("errorMessage", ""),
            },
        )
        await db.integrationsynclog.create(data={
            "tenant_id": integration.tenant_id,
            "integration_id": integration.id,
            "entity_type": "webhook",
            "status": "error",
            "records_synced": 0,
            "duration_ms": 0,
        })

    return standard_response(data={"received": True, "processed": True})
