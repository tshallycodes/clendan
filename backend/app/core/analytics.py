"""
PostHog analytics — fire-and-forget event tracking.
All calls are non-blocking: posthog batches and flushes in a background thread.
Never log financial data — only trace IDs and aggregate metrics.
"""
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger, get_trace_id

_logger = get_logger(__name__)
_posthog = None


def _get_client():
    global _posthog
    if _posthog is not None:
        return _posthog
    settings = get_settings()
    if not settings.posthog_api_key:
        return None
    try:
        import posthog as ph
        ph.project_api_key = settings.posthog_api_key
        ph.host = settings.posthog_host
        ph.on_error = lambda err, items: _logger.error("posthog_error", extra={"error": str(err)})
        _posthog = ph
    except ImportError:
        _logger.warning("posthog_not_installed — analytics disabled")
    return _posthog


def track_execution(
    tenant_id: str,
    decision: str,
    confidence: float,
    worker_type: str,
    duration_ms: Optional[int] = None,
) -> None:
    """Track an agent execution outcome. No financial amounts — decision + confidence only."""
    ph = _get_client()
    if ph is None:
        return
    try:
        ph.capture(
            distinct_id=tenant_id,
            event="agent_execution",
            properties={
                "decision": decision,
                "confidence": round(confidence, 2),
                "worker_type": worker_type,
                "duration_ms": duration_ms,
                "trace_id": get_trace_id(),
            },
        )
    except Exception as exc:
        _logger.error("analytics_capture_failed", extra={"error": str(exc)})


def track_approval(
    tenant_id: str,
    action: str,
    time_to_respond_seconds: Optional[float] = None,
) -> None:
    """Track an approval response."""
    ph = _get_client()
    if ph is None:
        return
    try:
        ph.capture(
            distinct_id=tenant_id,
            event="approval_responded",
            properties={
                "action": action,
                "time_to_respond_seconds": time_to_respond_seconds,
                "trace_id": get_trace_id(),
            },
        )
    except Exception as exc:
        _logger.error("analytics_capture_failed", extra={"error": str(exc)})


def track_worker_status(tenant_id: str, worker_type: str, status: str) -> None:
    """Track worker status changes."""
    ph = _get_client()
    if ph is None:
        return
    try:
        ph.capture(
            distinct_id=tenant_id,
            event="worker_status_changed",
            properties={"worker_type": worker_type, "status": status, "trace_id": get_trace_id()},
        )
    except Exception as exc:
        _logger.error("analytics_capture_failed", extra={"error": str(exc)})
