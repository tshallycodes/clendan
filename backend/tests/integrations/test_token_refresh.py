"""
Tests for the token manager — expiry checks and refresh dispatch.

Covers:
- Fresh token returned unchanged (expiry far in future)
- Expired token triggers refresh
- Near-expiry token (within 5-minute buffer) triggers refresh
- Missing integration raises ValueError
- No token_expiry_at skips expiry check and returns token as-is
"""

import json
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from app.integrations.token_manager import get_valid_token, REFRESH_BUFFER_SECONDS
except ImportError as exc:
    pytest.skip(f"token_manager not available: {exc}", allow_module_level=True)


def _make_integration(access_token: str, expiry_delta: timedelta | None, integration_type: str = "xero") -> MagicMock:
    """Returns a mock integration object with the given token and optional expiry."""
    m = MagicMock()
    m.id = "intg_001"
    m.type = integration_type
    m.tenant_id = "tenant_001"

    creds: dict = {
        "access_token": access_token,
        "refresh_token": "ref_xyz",
    }
    if expiry_delta is not None:
        creds["token_expiry_at"] = (datetime.now(UTC) + expiry_delta).isoformat()

    m.encrypted_credentials = json.dumps(creds)
    return m


def _make_db(integration) -> AsyncMock:
    db = AsyncMock()
    db.integration.find_unique.return_value = integration
    db.integration.update.return_value = integration
    return db


@pytest.mark.asyncio
async def test_fresh_token_returned_unchanged():
    """token_expiry_at far in future → no refresh, stored token returned."""
    integration = _make_integration("tok_fresh", timedelta(hours=2))
    db = _make_db(integration)

    with patch("app.integrations.token_manager._refresh_and_store") as mock_refresh:
        token = await get_valid_token("intg_001", db)

    assert token == "tok_fresh"
    mock_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh():
    """token_expiry_at in the past → refresh called, new token returned."""
    integration = _make_integration("tok_old", timedelta(hours=-1))
    db = _make_db(integration)

    new_creds = {"access_token": "tok_new", "refresh_token": "ref_xyz"}

    with patch(
        "app.integrations.token_manager._refresh_and_store",
        new=AsyncMock(return_value=new_creds),
    ) as mock_refresh:
        token = await get_valid_token("intg_001", db)

    assert token == "tok_new"
    mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_near_expiry_triggers_refresh():
    """token_expiry_at within REFRESH_BUFFER_SECONDS → refresh called."""
    # 30 seconds before the buffer threshold — should trigger refresh
    near_expiry = timedelta(seconds=REFRESH_BUFFER_SECONDS - 30)
    integration = _make_integration("tok_near", near_expiry)
    db = _make_db(integration)

    new_creds = {"access_token": "tok_refreshed", "refresh_token": "ref_xyz"}

    with patch(
        "app.integrations.token_manager._refresh_and_store",
        new=AsyncMock(return_value=new_creds),
    ) as mock_refresh:
        token = await get_valid_token("intg_001", db)

    assert token == "tok_refreshed"
    mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_missing_integration_raises_value_error():
    """find_unique returning None must raise ValueError."""
    db = AsyncMock()
    db.integration.find_unique.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await get_valid_token("intg_missing", db)


@pytest.mark.asyncio
async def test_no_expiry_skips_check_returns_token():
    """Credentials without token_expiry_at must return access_token without refreshing."""
    integration = _make_integration("tok_no_expiry", expiry_delta=None)
    db = _make_db(integration)

    with patch("app.integrations.token_manager._refresh_and_store") as mock_refresh:
        token = await get_valid_token("intg_001", db)

    assert token == "tok_no_expiry"
    mock_refresh.assert_not_called()
