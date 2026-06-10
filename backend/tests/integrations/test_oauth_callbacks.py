"""
Tests for OAuth callback and API-key connect endpoints.

Covers:
- QuickBooks callback: successful code exchange → integration created, status "connected"
- QuickBooks callback: invalid state (no colon) → 400
- QuickBooks callback: tenant not found → 404
- GoCardless connect: valid API key → 200 with status "syncing"
- GoCardless connect: invalid API key (401 from GoCardless) → 400
"""

import pytest
import json

try:
    from fastapi.testclient import TestClient
    from unittest.mock import patch, AsyncMock, MagicMock
    import httpx
except ImportError as exc:
    pytest.skip(f"required packages not available: {exc}", allow_module_level=True)

try:
    from app.main import create_app
    from app.core.security import get_current_user
    from app.core.config import get_settings
    from app.core.db import get_db_dep
except ImportError as exc:
    pytest.skip(f"app modules not available: {exc}", allow_module_level=True)


TENANT_ID = "tenant_test_001"
ORG_ID = "org_test_001"
AUTH_HEADER = {"Authorization": "Bearer fake-test-token"}


def _fake_current_user():
    """Returns a CurrentUser-like object for dependency override."""
    from app.core.security import CurrentUser
    return CurrentUser(
        user_id="user_001",
        org_id=ORG_ID,
        tenant_id=TENANT_ID,
        email="test@example.com",
        role="owner",
    )


def _make_tenant_mock() -> MagicMock:
    tenant = MagicMock()
    tenant.id = TENANT_ID
    return tenant


def _make_integration_mock(integration_id: str = "intg_qb_001") -> MagicMock:
    intg = MagicMock()
    intg.id = integration_id
    intg.status = "connected"
    return intg


def _get_client_with_overrides(extra_overrides: dict | None = None) -> TestClient:
    get_settings.cache_clear()
    app = create_app()

    # Override auth dependency so tests don't need a real Clerk JWT
    app.dependency_overrides[get_current_user] = _fake_current_user

    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# QuickBooks callback
# ---------------------------------------------------------------------------

def test_quickbooks_callback_success():
    """Valid code + state → integration created with status 'connected'."""
    tenant_mock = _make_tenant_mock()
    integration_mock = _make_integration_mock()

    db_mock = AsyncMock()
    db_mock.tenant.find_unique.return_value = tenant_mock
    db_mock.integration.find_first.return_value = None  # no existing integration
    db_mock.integration.create.return_value = integration_mock

    fake_tokens = {
        "access_token": "qb_tok_abc",
        "refresh_token": "qb_ref_xyz",
        "token_expiry_at": "2099-01-01T00:00:00+00:00",
    }
    company_info = {"company_name": "Acme Ltd", "realm_id": "realm_123"}

    with (
        patch("app.api.v1.integrations.qb.exchange_code", new=AsyncMock(return_value=fake_tokens)),
        patch("app.api.v1.integrations.qb.get_company_info", new=AsyncMock(return_value=company_info)),
    ):
        client = _get_client_with_overrides({get_db_dep: lambda: db_mock})
        response = client.get(
            f"/v1/integrations/quickbooks/callback?code=auth_code&state={TENANT_ID}:nonce_abc&realmId=realm_123"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "connected"
    assert body["data"]["realm_id"] == "realm_123"


def test_quickbooks_callback_invalid_state():
    """State without colon separator → 400."""
    db_mock = AsyncMock()

    client = _get_client_with_overrides({get_db_dep: lambda: db_mock})
    response = client.get(
        "/v1/integrations/quickbooks/callback?code=auth_code&state=invalidsate&realmId=realm_123"
    )

    assert response.status_code == 400


def test_quickbooks_callback_tenant_not_found():
    """Tenant lookup returns None → 404."""
    db_mock = AsyncMock()
    db_mock.tenant.find_unique.return_value = None

    client = _get_client_with_overrides({get_db_dep: lambda: db_mock})
    response = client.get(
        f"/v1/integrations/quickbooks/callback?code=auth_code&state={TENANT_ID}:nonce&realmId=realm_123"
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GoCardless connect
# ---------------------------------------------------------------------------

def test_gocardless_connect_valid_api_key():
    """Valid GoCardless API key → 200, status syncing."""
    db_mock = AsyncMock()
    integration_mock = _make_integration_mock("intg_gc_001")
    integration_mock.status = "syncing"
    db_mock.integration.find_first.return_value = None  # no existing integration
    db_mock.integration.create.return_value = integration_mock

    creditor_info = {"creditors": [{"id": "CR001", "name": "Test Creditor"}], "environment": "sandbox"}

    with (
        patch(
            "app.api.v1.gocardless.gc.validate_api_key",
            new=AsyncMock(return_value=creditor_info),
        ),
        patch(
            "app.api.v1.gocardless.encrypt_credentials",
            return_value="encrypted_blob",
        ),
        patch(
            "app.api.v1.gocardless.enqueue_gocardless_sync",
            new=AsyncMock(),
        ),
    ):
        client = _get_client_with_overrides({get_db_dep: lambda: db_mock})
        response = client.post(
            "/v1/integrations/gocardless/connect",
            json={"access_token": "gc_key_abc", "environment": "sandbox"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "syncing"


def test_gocardless_connect_invalid_api_key():
    """GoCardless returns 401 on validate_api_key → 400 with structured error."""
    db_mock = AsyncMock()

    # Build a minimal httpx.HTTPStatusError for a 401 response
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    http_error = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=mock_response,
    )

    with patch(
        "app.api.v1.gocardless.gc.validate_api_key",
        new=AsyncMock(side_effect=http_error),
    ):
        client = _get_client_with_overrides({get_db_dep: lambda: db_mock})
        response = client.post(
            "/v1/integrations/gocardless/connect",
            json={"access_token": "bad_key", "environment": "sandbox"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 400
