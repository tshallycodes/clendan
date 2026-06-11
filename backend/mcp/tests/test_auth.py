"""
tests/test_auth.py — Unit tests for the auth module.

Tests API key handling, header generation, and error mapping without
making any real HTTP calls.
"""
import os
import pytest
import httpx
import respx

from clendan_mcp.auth import (
    MCPError,
    api_get,
    api_post,
    api_patch,
    _get_headers,
    _map_error,
)


# ---------------------------------------------------------------------------
# MCPError tests
# ---------------------------------------------------------------------------

def test_mcp_error_str():
    err = MCPError("Something went wrong", status_code=400)
    assert str(err) == "Something went wrong"
    assert err.status_code == 400


def test_mcp_error_to_dict():
    err = MCPError("Bad input", status_code=422)
    assert err.to_dict() == {"error": "Bad input", "status_code": 422}


def test_mcp_error_no_status():
    err = MCPError("No key set")
    assert err.status_code is None


# ---------------------------------------------------------------------------
# API key tests
# ---------------------------------------------------------------------------

def test_get_headers_raises_when_no_key(monkeypatch):
    monkeypatch.delenv("CLENDAN_API_KEY", raising=False)
    # Override module-level var too
    import clendan_mcp.auth as auth_module
    original = auth_module.CLENDAN_API_KEY
    auth_module.CLENDAN_API_KEY = ""
    try:
        with pytest.raises(MCPError, match="CLENDAN_API_KEY is not set"):
            _get_headers()
    finally:
        auth_module.CLENDAN_API_KEY = original


def test_get_headers_with_key(monkeypatch):
    import clendan_mcp.auth as auth_module
    original = auth_module.CLENDAN_API_KEY
    auth_module.CLENDAN_API_KEY = "test_key_123"
    try:
        headers = _get_headers()
        assert headers["Authorization"] == "Bearer test_key_123"
        assert headers["Content-Type"] == "application/json"
    finally:
        auth_module.CLENDAN_API_KEY = original


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------

def test_map_error_known_status():
    response = httpx.Response(404, json={"detail": "Not found"})
    err = _map_error(response)
    assert err.status_code == 404
    assert "not found" in str(err).lower()


def test_map_error_unknown_status():
    response = httpx.Response(599)
    err = _map_error(response)
    assert err.status_code == 599
    assert "599" in str(err)


def test_map_error_includes_detail():
    response = httpx.Response(400, json={"error": "amount_minor is required"})
    err = _map_error(response)
    assert "amount_minor" in str(err)


# ---------------------------------------------------------------------------
# HTTP helper tests (using respx to mock httpx)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_api_get_success(monkeypatch):
    import clendan_mcp.auth as auth_module
    auth_module.CLENDAN_API_KEY = "test_key"
    auth_module.CLENDAN_API_BASE = "https://api.clendan.com"

    respx.get("https://api.clendan.com/v1/tools").mock(
        return_value=httpx.Response(200, json={"data": {"workers": []}})
    )

    result = await api_get("/v1/tools")
    assert result == {"data": {"workers": []}}


@pytest.mark.asyncio
@respx.mock
async def test_api_get_401_raises_mcp_error(monkeypatch):
    import clendan_mcp.auth as auth_module
    auth_module.CLENDAN_API_KEY = "bad_key"
    auth_module.CLENDAN_API_BASE = "https://api.clendan.com"

    respx.get("https://api.clendan.com/v1/tools").mock(
        return_value=httpx.Response(401)
    )

    with pytest.raises(MCPError) as exc_info:
        await api_get("/v1/tools")
    assert exc_info.value.status_code == 401
    assert "invalid" in str(exc_info.value).lower() or "authentication" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_api_post_success(monkeypatch):
    import clendan_mcp.auth as auth_module
    auth_module.CLENDAN_API_KEY = "test_key"
    auth_module.CLENDAN_API_BASE = "https://api.clendan.com"

    respx.post("https://api.clendan.com/v1/fraud/score").mock(
        return_value=httpx.Response(200, json={"data": {"risk_score": 0.1}})
    )

    result = await api_post("/v1/fraud/score", data={"transaction_id": "tx_1"})
    assert result == {"data": {"risk_score": 0.1}}


@pytest.mark.asyncio
@respx.mock
async def test_api_patch_success(monkeypatch):
    import clendan_mcp.auth as auth_module
    auth_module.CLENDAN_API_KEY = "test_key"
    auth_module.CLENDAN_API_BASE = "https://api.clendan.com"

    respx.patch("https://api.clendan.com/v1/tools/w_1/pause").mock(
        return_value=httpx.Response(200, json={"data": {"status": "inactive"}})
    )

    result = await api_patch("/v1/tools/w_1/pause")
    assert result == {"data": {"status": "inactive"}}
