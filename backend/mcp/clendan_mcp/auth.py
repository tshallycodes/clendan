"""
auth.py — API key handling and HTTP helpers for calling the Clendan REST API.

All tools use api_get() and api_post() from this module. Never make raw
httpx calls in tool files — always go through these helpers so error
mapping is consistent.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

CLENDAN_API_BASE = os.getenv("CLENDAN_API_BASE", "https://api.clendan.com")
CLENDAN_API_KEY = os.getenv("CLENDAN_API_KEY", "")

# User-friendly error messages for common HTTP status codes
_STATUS_MESSAGES: dict[int, str] = {
    400: "Bad request — check your input parameters.",
    401: "Authentication failed — your API key is invalid or expired.",
    403: "Access denied — you do not have permission for this action.",
    404: "Resource not found.",
    409: "Conflict — this action cannot be performed in the current state.",
    410: "This approval has expired and can no longer be acted on.",
    422: "Validation error — one or more input values are invalid.",
    429: "Rate limit exceeded — slow down and retry.",
    500: "Clendan server error — please try again shortly.",
    502: "Clendan is temporarily unavailable — please try again.",
    503: "Clendan is under maintenance — please try again later.",
}


class MCPError(Exception):
    """Raised by tool helpers when the API call cannot succeed.

    Always contains a user-friendly message suitable for returning to Claude
    without leaking internal error details.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": str(self), "status_code": self.status_code}


def _require_api_key() -> str:
    key = CLENDAN_API_KEY or os.getenv("CLENDAN_API_KEY", "")
    if not key:
        raise MCPError(
            "CLENDAN_API_KEY is not set. "
            "Get your API key from https://app.clendan.com/dashboard/developer-api "
            "and set it in your MCP config."
        )
    return key


def _get_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_require_api_key()}",
        "Content-Type": "application/json",
    }


def _map_error(response: httpx.Response) -> MCPError:
    """Convert an httpx error response to a user-friendly MCPError."""
    friendly = _STATUS_MESSAGES.get(
        response.status_code,
        f"Unexpected error from Clendan (HTTP {response.status_code}).",
    )
    try:
        body = response.json()
        detail = body.get("error") or body.get("detail") or ""
        if detail:
            friendly = f"{friendly} Detail: {detail}"
    except Exception:
        pass
    return MCPError(friendly, status_code=response.status_code)


async def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Make an authenticated GET request to the Clendan API.

    Returns the parsed JSON response body.
    Raises MCPError on any non-2xx response.
    """
    base = os.getenv("CLENDAN_API_BASE", CLENDAN_API_BASE).rstrip("/")
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=_get_headers(), params=params)
        except httpx.ConnectError:
            raise MCPError("Cannot reach Clendan — check your internet connection or CLENDAN_API_BASE.")
        except httpx.TimeoutException:
            raise MCPError("Request to Clendan timed out — try again.")
        if not response.is_success:
            raise _map_error(response)
        return response.json()


async def api_post(
    path: str,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> Any:
    """Make an authenticated POST request to the Clendan API.

    When `files` is provided the request is sent as multipart/form-data.
    Returns the parsed JSON response body.
    Raises MCPError on any non-2xx response.
    """
    base = os.getenv("CLENDAN_API_BASE", CLENDAN_API_BASE).rstrip("/")
    url = f"{base}{path}"
    key = _require_api_key()

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if files:
                # Multipart — don't set Content-Type header (httpx sets boundary)
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                    files=files,
                    timeout=60.0,
                )
            else:
                response = await client.post(
                    url,
                    headers=_get_headers(),
                    json=data,
                    timeout=30.0,
                )
        except httpx.ConnectError:
            raise MCPError("Cannot reach Clendan — check your internet connection or CLENDAN_API_BASE.")
        except httpx.TimeoutException:
            raise MCPError("Request to Clendan timed out — try again.")
        if not response.is_success:
            raise _map_error(response)
        return response.json()


async def api_patch(path: str, data: dict[str, Any] | None = None) -> Any:
    """Make an authenticated PATCH request to the Clendan API."""
    base = os.getenv("CLENDAN_API_BASE", CLENDAN_API_BASE).rstrip("/")
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.patch(
                url, headers=_get_headers(), json=data or {}
            )
        except httpx.ConnectError:
            raise MCPError("Cannot reach Clendan — check your internet connection or CLENDAN_API_BASE.")
        except httpx.TimeoutException:
            raise MCPError("Request to Clendan timed out — try again.")
        if not response.is_success:
            raise _map_error(response)
        return response.json()
