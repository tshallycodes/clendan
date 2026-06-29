"""
Phase 7 hardening tests.
Covers: rate limiter logic, Plaid webhook verification, DLQ operations, analytics (no-op when unconfigured).
"""
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import CurrentUser

FAKE_USER = CurrentUser(
    user_id="user_test",
    org_id="org_test",
    tenant_id="tenant_test",
    email="test@example.com",
    role="owner",
)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def test_rate_limit_path_buckets():
    """Verify the correct limits are selected for each path type."""
    from app.core.rate_limit import _get_limit

    parse_limit, parse_window = _get_limit("/parse/invoice")
    assert parse_limit == 20
    assert parse_window == 60

    agents_limit, _ = _get_limit("/agents/abc/run")
    assert agents_limit == 30

    general_limit, _ = _get_limit("/dashboard/stats")
    assert general_limit == 200


def test_rate_limit_exempt_paths():
    """Health and ready endpoints are never rate-limited."""
    from app.core.rate_limit import _EXEMPT
    assert "/health" in _EXEMPT
    assert "/ready" in _EXEMPT


# ---------------------------------------------------------------------------
# Plaid webhook verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plaid_webhook_rejects_expired_token():
    """Token older than 5 minutes must be rejected."""
    from app.api.v1.webhooks.plaid import _verify_plaid_token
    from fastapi import HTTPException

    # Create a token with iat far in the past
    stale_iat = int(time.time()) - 400  # 400s ago > MAX_TOKEN_AGE_SECONDS (300)

    mock_payload = {"iat": stale_iat, "request_body_sha256": "abc"}
    mock_key = {"kty": "EC", "crv": "P-256"}

    with (
        patch("app.api.v1.webhooks.plaid._fetch_plaid_key", AsyncMock(return_value=mock_key)),
        patch("app.api.v1.webhooks.plaid.jwt.get_unverified_header", return_value={"kid": "k1", "alg": "ES256"}),
        patch("app.api.v1.webhooks.plaid.jwt.decode", return_value=mock_payload),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _verify_plaid_token("fake.jwt.token")
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_plaid_webhook_rejects_missing_kid():
    """Token without a key ID in its header must be rejected."""
    from app.api.v1.webhooks.plaid import _verify_plaid_token
    from fastapi import HTTPException

    with patch("app.api.v1.webhooks.plaid.jwt.get_unverified_header", return_value={"alg": "ES256"}):
        with pytest.raises(HTTPException) as exc_info:
            await _verify_plaid_token("fake.jwt.token")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_plaid_webhook_accepts_valid_token():
    """A fresh token with valid signature must pass verification."""
    from app.api.v1.webhooks.plaid import _verify_plaid_token

    fresh_iat = int(time.time()) - 10
    mock_payload = {"iat": fresh_iat, "request_body_sha256": "abc"}
    mock_key = {"kty": "EC"}

    with (
        patch("app.api.v1.webhooks.plaid._fetch_plaid_key", AsyncMock(return_value=mock_key)),
        patch("app.api.v1.webhooks.plaid.jwt.get_unverified_header", return_value={"kid": "k1"}),
        patch("app.api.v1.webhooks.plaid.jwt.decode", return_value=mock_payload),
    ):
        result = await _verify_plaid_token("valid.jwt.token")
    assert result["iat"] == fresh_iat


# ---------------------------------------------------------------------------
# DLQ operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dlq_list_returns_parsed_entries():
    """DLQ entries should be parsed from JSON and returned."""
    entry = {"job_id": "j1", "function": "run_invoice_job", "error": "timeout"}
    mock_pool = MagicMock()
    mock_pool.lrange = AsyncMock(return_value=[json.dumps(entry).encode()])

    with patch("app.api.v1.dlq.get_queue_pool", AsyncMock(return_value=mock_pool)):
        from app.api.v1.dlq import list_dlq
        result = await list_dlq(current_user=FAKE_USER)

    assert result["data"]["count"] == 1
    assert result["data"]["jobs"][0]["job_id"] == "j1"


@pytest.mark.asyncio
async def test_dlq_replay_removes_job():
    """Replaying a job must remove it from the DLQ list."""
    entry = {"job_id": "j1", "function": "run_invoice_job", "error": "timeout"}
    raw = json.dumps(entry).encode()

    mock_pool = MagicMock()
    mock_pool.lrange = AsyncMock(return_value=[raw])
    mock_pool.lrem = AsyncMock(return_value=1)

    with patch("app.api.v1.dlq.get_queue_pool", AsyncMock(return_value=mock_pool)):
        from app.api.v1.dlq import replay_job
        result = await replay_job("j1", current_user=FAKE_USER)

    mock_pool.lrem.assert_called_once_with("clendan:dlq", 1, raw)
    assert result["data"]["status"] == "removed_from_dlq"


# ---------------------------------------------------------------------------
# Analytics — no-op when PostHog key not configured
# ---------------------------------------------------------------------------

def test_analytics_noop_without_api_key():
    """PostHog tracking must be a no-op when POSTHOG_API_KEY is not set."""
    with patch("app.core.analytics.get_settings") as mock_settings:
        mock_settings.return_value.posthog_api_key = ""
        from app.core.analytics import _get_client
        import app.core.analytics as ana
        ana._posthog = None  # reset cached client
        client = _get_client()
    assert client is None


def test_analytics_track_execution_does_not_raise_when_unconfigured():
    """track_execution must not raise even when PostHog is not installed."""
    with patch("app.core.analytics.get_settings") as mock_settings:
        mock_settings.return_value.posthog_api_key = ""
        import app.core.analytics as ana
        ana._posthog = None
        ana.track_execution(
            tenant_id="t1",
            decision="auto_approved",
            confidence=0.95,
            tool_type="invoice_processing",
        )  # must not raise
