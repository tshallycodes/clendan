"""
tools/integrations.py — Integration status tools.

Integrations connect Clendan to external financial systems (QuickBooks,
Xero, Plaid, GoCardless, etc.). These tools let you check their health
and trigger manual resyncs.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get, api_post

# Known integration types and their status API paths
_INTEGRATION_PATHS: dict[str, str] = {
    "quickbooks": "/v1/integrations/quickbooks/status",
    "xero": "/v1/xero/status",
    "plaid": "/v1/plaid/status",
    "stripe": "/v1/stripe/status",
    "gocardless": "/v1/gocardless/status",
    "truelayer": "/v1/truelayer/status",
    "codat": "/v1/codat/status",
    "hubspot": "/v1/hubspot/status",
    "gmail": "/v1/gmail/status",
    "google_drive": "/v1/google-drive/status",
    "outlook": "/v1/outlook/status",
}

_SYNC_PATHS: dict[str, str] = {
    "quickbooks": "/v1/integrations/quickbooks/sync",
    "xero": "/v1/xero/sync",
    "plaid": "/v1/plaid/sync",
    "stripe": "/v1/stripe/sync",
    "gocardless": "/v1/gocardless/sync",
    "truelayer": "/v1/truelayer/sync",
    "codat": "/v1/codat/sync",
    "hubspot": "/v1/hubspot/sync",
    "gmail": "/v1/gmail/sync",
    "google_drive": "/v1/google-drive/sync",
    "outlook": "/v1/outlook/sync",
}


async def list_integrations() -> list[dict[str, Any]]:
    """
    List all integrations and their connection status.

    Checks all known integration types and returns the ones your account
    has configured, along with their current status.

    Returns a list of integration objects, each with:
        type (str): Integration type (e.g. "quickbooks", "xero", "plaid")
        status (str): "connected" | "disconnected" | "error" | "not_configured"
        connected_at (str | null): ISO 8601 timestamp when connection was established
        integration_id (str | null): Internal integration record ID
        error (str | null): Error message if status is "error"

    Returns an empty list if no integrations are configured.
    """
    results: list[dict[str, Any]] = []

    for integration_type, path in _INTEGRATION_PATHS.items():
        try:
            response = await api_get(path)
            body = response.get("data", response)
            results.append({
                "type": integration_type,
                **body,
            })
        except MCPError as exc:
            # 404 means not configured — include it with not_configured status
            if exc.status_code == 404:
                results.append({"type": integration_type, "status": "not_configured"})
            else:
                results.append({"type": integration_type, "status": "error", "error": str(exc)})
        except Exception as exc:
            results.append({"type": integration_type, "status": "error", "error": str(exc)})

    return results


async def get_integration_status(integration_type: str) -> dict[str, Any]:
    """
    Get detailed status of a specific integration.

    Args:
        integration_type: One of: quickbooks, xero, plaid, stripe, gocardless,
            truelayer, codat, hubspot, gmail, google_drive, outlook

    Returns:
        type (str): Integration type
        status (str): "connected" | "disconnected" | "error" | "not_configured"
        connected_at (str | null): When the integration was connected
        integration_id (str | null): Internal ID
        last_sync (str | null): ISO 8601 timestamp of most recent successful sync
        sync_count (int | null): Number of records synced
        error (str | null): Error detail if status is "error"

    If the integration is not connected, the response will include instructions
    on how to connect it via the Clendan dashboard.
    """
    integration_type = integration_type.lower().strip()
    if integration_type not in _INTEGRATION_PATHS:
        raise MCPError(
            f"Unknown integration type '{integration_type}'. "
            f"Supported types: {', '.join(sorted(_INTEGRATION_PATHS.keys()))}"
        )

    path = _INTEGRATION_PATHS[integration_type]
    try:
        response = await api_get(path)
        body = response.get("data", response)
        return {"type": integration_type, **body}
    except MCPError as exc:
        if exc.status_code == 404:
            return {
                "type": integration_type,
                "status": "not_configured",
                "message": (
                    f"The {integration_type} integration is not set up. "
                    f"Connect it at https://app.clendan.com/dashboard/integrations"
                ),
            }
        raise


async def trigger_sync(integration_type: str) -> dict[str, Any]:
    """
    Manually trigger a data resync for an integration.

    Useful when you need fresh data immediately rather than waiting for the
    next scheduled sync. The sync runs asynchronously — use the returned
    job_id to track progress.

    IMPORTANT: This only works for connected integrations. Check
    get_integration_status() first if you're unsure of the connection state.

    Args:
        integration_type: One of: quickbooks, xero, plaid, stripe, gocardless,
            truelayer, codat, hubspot, gmail, google_drive, outlook

    Returns:
        job_id (str): Sync job ID — you can poll the integration status to see
            when the sync completes
        integration_type (str): The integration being synced
        status (str): "queued" | "running"
        message (str): Human-readable status message
    """
    integration_type = integration_type.lower().strip()
    if integration_type not in _SYNC_PATHS:
        raise MCPError(
            f"Unknown integration type '{integration_type}'. "
            f"Supported types: {', '.join(sorted(_SYNC_PATHS.keys()))}"
        )

    path = _SYNC_PATHS[integration_type]
    try:
        response = await api_post(path, data={})
        body = response.get("data", response)
        return {"integration_type": integration_type, **body}
    except MCPError as exc:
        if exc.status_code == 404:
            raise MCPError(
                f"Cannot sync '{integration_type}' — it is not connected. "
                f"Connect it at https://app.clendan.com/dashboard/integrations"
            )
        raise
