"""
Tests for the CircuitBreaker implementation.

Covers:
- CLOSED state: successful calls pass through
- Opens after failure_threshold consecutive failures
- OPEN state: calls blocked with CircuitOpenError (no fn invocation)
- HALF_OPEN transition after recovery_timeout seconds
- HALF_OPEN success → circuit closes
- HALF_OPEN failure → circuit re-opens
"""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, patch

try:
    from app.integrations.quickbooks.circuit_breaker import (
        CircuitBreaker,
        CircuitOpenError,
        CircuitState,
    )
except ImportError as exc:
    pytest.skip(f"circuit_breaker not available: {exc}", allow_module_level=True)


FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 60


def _make_cb() -> CircuitBreaker:
    return CircuitBreaker(
        "test",
        failure_threshold=FAILURE_THRESHOLD,
        recovery_timeout=RECOVERY_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# CLOSED state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_closed_state_passes_through():
    """Successful call in CLOSED state: result returned, state remains CLOSED."""
    cb = _make_cb()
    mock_fn = AsyncMock(return_value="result")

    result = await cb.call(mock_fn)

    assert result == "result"
    assert cb.state == CircuitState.CLOSED
    mock_fn.assert_called_once()


@pytest.mark.asyncio
async def test_failure_below_threshold_stays_closed():
    """Failures below threshold must NOT open the circuit."""
    cb = _make_cb()

    async def failing_fn():
        raise RuntimeError("transient")

    for _ in range(FAILURE_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await cb.call(failing_fn)

    assert cb._state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# OPEN state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_opens_after_threshold_failures():
    """Exactly failure_threshold consecutive failures → circuit becomes OPEN."""
    cb = _make_cb()

    async def failing_fn():
        raise RuntimeError("fail")

    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(RuntimeError):
            await cb.call(failing_fn)

    assert cb._state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_circuit_blocks_calls():
    """OPEN circuit must raise CircuitOpenError without invoking the function."""
    cb = _make_cb()

    async def failing_fn():
        raise RuntimeError("fail")

    # Trip the circuit
    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(RuntimeError):
            await cb.call(failing_fn)

    mock_fn = AsyncMock(return_value="should_not_be_called")

    with pytest.raises(CircuitOpenError):
        await cb.call(mock_fn)

    mock_fn.assert_not_called()


# ---------------------------------------------------------------------------
# HALF_OPEN transition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_half_open_after_timeout():
    """After recovery_timeout elapses, state property returns HALF_OPEN."""
    cb = _make_cb()

    async def failing_fn():
        raise RuntimeError("fail")

    # Trip the circuit
    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(RuntimeError):
            await cb.call(failing_fn)

    assert cb._state == CircuitState.OPEN

    # Advance simulated time past recovery_timeout
    future_time = datetime.now(UTC) + timedelta(seconds=RECOVERY_TIMEOUT + 1)

    with patch("app.integrations.quickbooks.circuit_breaker.datetime") as mock_dt:
        mock_dt.now.return_value = future_time
        state = cb.state

    assert state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit():
    """Probe call succeeding in HALF_OPEN state → circuit returns to CLOSED."""
    cb = _make_cb()

    async def failing_fn():
        raise RuntimeError("fail")

    # Trip the circuit
    for _ in range(FAILURE_THRESHOLD):
        with pytest.raises(RuntimeError):
            await cb.call(failing_fn)

    # Force HALF_OPEN by directly setting state and a past opened_at
    cb._state = CircuitState.HALF_OPEN

    mock_fn = AsyncMock(return_value="probe_ok")
    result = await cb.call(mock_fn)

    assert result == "probe_ok"
    assert cb._state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit():
    """Probe call failing in HALF_OPEN state → circuit goes back to OPEN."""
    cb = _make_cb()

    # Force HALF_OPEN directly
    cb._state = CircuitState.HALF_OPEN

    async def probe_fail():
        raise RuntimeError("probe failed")

    with pytest.raises(RuntimeError):
        await cb.call(probe_fail)

    assert cb._state == CircuitState.OPEN
