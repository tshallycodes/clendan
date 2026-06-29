"""
Tests for webhook signature verification.

Covers:
- GoCardless webhook: valid HMAC-SHA256 signature â†’ 200
- GoCardless webhook: invalid signature â†’ 401
- GoCardless webhook: missing Webhook-Signature header â†’ 422 (FastAPI) or 401
- Stripe: valid Stripe-style HMAC signature â†’ verify_stripe_signature returns True
- Stripe: invalid signature â†’ verify_stripe_signature returns False
"""

import hashlib
import hmac
import json
import time
import pytest

try:
    from fastapi.testclient import TestClient
    from unittest.mock import patch, AsyncMock, MagicMock
except ImportError as exc:
    pytest.skip(f"fastapi or mock not available: {exc}", allow_module_level=True)

try:
    from app.integrations.stripe.client import verify_stripe_signature
except ImportError as exc:
    pytest.skip(f"stripe client not available: {exc}", allow_module_level=True)

GOCARDLESS_WEBHOOK_SECRET = "test-gocardless-webhook-secret"
STRIPE_WEBHOOK_SECRET = "test-stripe-webhook-secret"


def _sign_gocardless(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _sign_stripe(payload: bytes, secret: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}.{payload.decode()}"
    return hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()


def _get_test_client() -> TestClient:
    from app.main import create_app
    from app.core.config import get_settings
    get_settings.cache_clear()
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _gocardless_payload() -> bytes:
    return json.dumps({
        "events": [
            {"id": "EV001", "resource_type": "payments", "action": "paid_out"}
        ]
    }).encode()


# ---------------------------------------------------------------------------
# GoCardless webhook tests
# ---------------------------------------------------------------------------

def test_gocardless_valid_signature():
    """Valid HMAC-SHA256 signature â†’ 200."""
    payload = _gocardless_payload()
    signature = _sign_gocardless(payload, GOCARDLESS_WEBHOOK_SECRET)

    with (
        patch("app.core.config.Settings.gocardless_webhook_secret", GOCARDLESS_WEBHOOK_SECRET, create=True),
        patch("app.api.v1.webhooks.gocardless.get_settings") as mock_settings,
        patch("app.api.v1.webhooks.gocardless.get_db") as mock_get_db,
        patch("app.api.v1.webhooks.gocardless.enqueue_gocardless_sync", new=AsyncMock()),
    ):
        settings = MagicMock()
        settings.gocardless_webhook_secret = GOCARDLESS_WEBHOOK_SECRET
        mock_settings.return_value = settings

        db_mock = AsyncMock()
        integration_mock = MagicMock()
        integration_mock.id = "intg_gc_001"
        integration_mock.tenant_id = "tenant_001"
        db_mock.integration.find_first.return_value = integration_mock
        mock_get_db.return_value = db_mock

        client = _get_test_client()
        response = client.post(
            "/webhooks/gocardless",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Webhook-Signature": signature,
            },
        )

    assert response.status_code == 200


def test_gocardless_invalid_signature():
    """Wrong signature â†’ 401."""
    payload = _gocardless_payload()
    wrong_signature = _sign_gocardless(payload, "wrong-secret")

    with (
        patch("app.api.v1.webhooks.gocardless.get_settings") as mock_settings,
        patch("app.api.v1.webhooks.gocardless.get_db") as mock_get_db,
    ):
        settings = MagicMock()
        settings.gocardless_webhook_secret = GOCARDLESS_WEBHOOK_SECRET
        mock_settings.return_value = settings

        mock_get_db.return_value = AsyncMock()

        client = _get_test_client()
        response = client.post(
            "/webhooks/gocardless",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "Webhook-Signature": wrong_signature,
            },
        )

    assert response.status_code == 401


def test_gocardless_missing_signature_header():
    """Request without Webhook-Signature header â†’ FastAPI returns 422 (missing required header)."""
    payload = _gocardless_payload()

    with (
        patch("app.api.v1.webhooks.gocardless.get_settings") as mock_settings,
        patch("app.api.v1.webhooks.gocardless.get_db") as mock_get_db,
    ):
        settings = MagicMock()
        settings.gocardless_webhook_secret = GOCARDLESS_WEBHOOK_SECRET
        mock_settings.return_value = settings

        mock_get_db.return_value = AsyncMock()

        client = _get_test_client()
        response = client.post(
            "/webhooks/gocardless",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

    # FastAPI returns 422 for a missing required Header(...) field
    assert response.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Stripe signature verification unit tests (no HTTP â€” testing the function directly)
# ---------------------------------------------------------------------------

def test_stripe_valid_signature():
    """verify_stripe_signature with correct HMAC â†’ returns True."""
    payload = b'{"type":"invoice.payment_succeeded","data":{}}'
    timestamp = int(time.time())
    sig = _sign_stripe(payload, STRIPE_WEBHOOK_SECRET, timestamp)
    sig_header = f"t={timestamp},v1={sig}"

    result = verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    assert result is True


def test_stripe_invalid_signature():
    """verify_stripe_signature with wrong secret â†’ returns False."""
    payload = b'{"type":"invoice.payment_succeeded","data":{}}'
    timestamp = int(time.time())
    sig = _sign_stripe(payload, "wrong-secret", timestamp)
    sig_header = f"t={timestamp},v1={sig}"

    result = verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    assert result is False
