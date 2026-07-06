"""
Prometheus instrumentation for the Clendan API.

Metrics are optional: if ``prometheus_client`` is not installed the module degrades
to no-ops and ``/metrics`` returns a plain notice, so the app never fails to import
or serve because observability tooling is missing. Install adds it in production
(see ``prometheus-client`` in pyproject).

Labels are kept low-cardinality on purpose — requests are labelled by the matched
route template (e.g. ``/execute/{execution_id}``), never the raw URL, to avoid an
unbounded time series per id.
"""
from __future__ import annotations

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    METRICS_ENABLED = True
except ImportError:  # pragma: no cover - exercised only when the dep is absent
    METRICS_ENABLED = False

_PLAINTEXT = "text/plain; version=0.0.4; charset=utf-8"

if METRICS_ENABLED:
    REQUEST_COUNT = Counter(
        "clendan_http_requests_total",
        "Total HTTP requests processed, labelled by method, route template and status.",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "clendan_http_request_duration_seconds",
        "HTTP request latency in seconds, labelled by method and route template.",
        ["method", "path"],
    )


def observe_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    """Record one completed HTTP request. No-op when Prometheus is unavailable."""
    if not METRICS_ENABLED:
        return
    REQUEST_COUNT.labels(method=method, path=path, status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(duration_seconds)


def metrics_payload() -> tuple[bytes, str]:
    """Return the Prometheus exposition payload and its content type.

    When Prometheus is not installed, returns a human-readable notice so the
    endpoint is still reachable (and monitorable) rather than 404/500.
    """
    if not METRICS_ENABLED:
        return (
            b"# prometheus_client is not installed; metrics are disabled.\n",
            _PLAINTEXT,
        )
    return generate_latest(), CONTENT_TYPE_LATEST
