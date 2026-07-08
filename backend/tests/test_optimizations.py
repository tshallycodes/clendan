"""
Tests covering the optimization pass: policy-engine edge cases, dispatch-mapping
integrity, Prometheus metrics helpers, and the new /metrics and
/.well-known/security.txt endpoints. None of these require a live database.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.dispatch import (
    EVENT_TYPE_TO_JOB,
    EVENT_TYPE_TO_TOOL_TYPE,
    TOOL_TYPE_TO_JOB,
)
from app.core.metrics import metrics_payload, observe_request
from app.main import app
from app.policy.engine import Decision, evaluate_invoice_policy, evaluate_policy

_BASE = dict(
    verified_suppliers=["Acme Ltd"],
    allowed_currencies=["GBP", "USD"],
    auto_threshold_minor=50_000,
    block_threshold_minor=500_000,
)


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def test_disallowed_currency_is_blocked(self):
        result = evaluate_policy(amount_minor=1000, currency="JPY", vendor="Acme Ltd", **_BASE)
        assert result.decision is Decision.BLOCKED
        assert result.rule_triggered == "currency_allowlist"

    def test_amount_over_block_threshold_is_blocked(self):
        result = evaluate_policy(amount_minor=600_000, currency="GBP", vendor="Acme Ltd", **_BASE)
        assert result.decision is Decision.BLOCKED
        assert result.rule_triggered == "amount_block_threshold"

    def test_amount_over_auto_threshold_needs_approval(self):
        result = evaluate_policy(amount_minor=60_000, currency="GBP", vendor="Acme Ltd", **_BASE)
        assert result.decision is Decision.APPROVAL_REQUIRED
        assert result.rule_triggered == "amount_approve_threshold"

    def test_unverified_supplier_needs_approval(self):
        result = evaluate_policy(amount_minor=1000, currency="GBP", vendor="Unknown Co", **_BASE)
        assert result.decision is Decision.APPROVAL_REQUIRED
        assert result.rule_triggered == "verified_supplier"

    def test_clean_invoice_auto_approves(self):
        result = evaluate_policy(amount_minor=1000, currency="GBP", vendor="Acme Ltd", **_BASE)
        assert result.decision is Decision.AUTO_APPROVED

    def test_low_ocr_confidence_is_blocked(self):
        result = evaluate_invoice_policy(
            amount_minor=1000, currency="GBP", vendor="Acme Ltd", ocr_confidence=0.5, **_BASE
        )
        assert result.decision is Decision.BLOCKED
        assert result.rule_triggered == "ocr_confidence"

    def test_duplicate_invoice_is_blocked(self):
        result = evaluate_invoice_policy(
            amount_minor=1000, currency="GBP", vendor="Acme Ltd",
            ocr_confidence=0.99, is_duplicate=True, **_BASE,
        )
        assert result.decision is Decision.BLOCKED
        assert result.rule_triggered == "duplicate_invoice"

    def test_stale_invoice_is_blocked(self):
        old = date.today() - timedelta(days=400)
        result = evaluate_invoice_policy(
            amount_minor=1000, currency="GBP", vendor="Acme Ltd", ocr_confidence=0.99,
            invoice_date=old, max_invoice_age_days=180, **_BASE,
        )
        assert result.decision is Decision.BLOCKED
        assert result.rule_triggered == "invoice_age"


# ---------------------------------------------------------------------------
# Dispatch mapping integrity
# ---------------------------------------------------------------------------

class TestDispatchIntegrity:
    def test_every_event_job_has_a_tool_type(self):
        missing = [e for e in EVENT_TYPE_TO_JOB if e not in EVENT_TYPE_TO_TOOL_TYPE]
        assert missing == [], f"event types missing a tool_type mapping: {missing}"

    def test_active_tools_are_all_routable(self):
        active = {
            "invoice_processing", "receipt_processing", "reconciliation",
            "spend_control", "tax_compliance", "financial_reporting", "payment_run",
            "document_intelligence",
        }
        missing = [t for t in active if t not in TOOL_TYPE_TO_JOB]
        assert missing == [], f"active tools missing from TOOL_TYPE_TO_JOB: {missing}"


# ---------------------------------------------------------------------------
# Metrics helpers + endpoints
# ---------------------------------------------------------------------------

class TestObservability:
    def test_observe_request_never_raises(self):
        # Safe whether or not prometheus_client is installed.
        observe_request("GET", "/health", 200, 0.01)

    def test_metrics_payload_shape(self):
        payload, content_type = metrics_payload()
        assert isinstance(payload, bytes)
        assert isinstance(content_type, str) and content_type

    def test_metrics_endpoint_reachable(self):
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_security_txt_endpoint(self):
        client = TestClient(app)
        response = client.get("/.well-known/security.txt")
        assert response.status_code == 200
        assert "security@clendan.com" in response.text
        assert "Expires:" in response.text
