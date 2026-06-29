"""
Tests for the developer-facing execute API:
  POST /v1/execute   â€” enqueue any tool by API key
  GET  /v1/execute/{execution_id} â€” poll for result

All 13 frontend tool types must be reachable through the API.
DB and arq queue are mocked â€” no live services required.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.execute import TOOL_TYPE_TO_EVENT
from app.main import app

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_VALID_KEY = "ck_live_" + "a" * 32
_KEY_HASH = hashlib.sha256(_VALID_KEY.encode()).hexdigest()
_TENANT_ID = "tenant_test"
_TOOL_ID = "tool_test"
_EXECUTION_ID = "exec_test"

VALID_HEADERS = {
    "Authorization": _VALID_KEY,
    "Idempotency-Key": "idem_key_001",
}

_FAKE_API_KEY = MagicMock(
    id="apikey_001",
    tenant_id=_TENANT_ID,
    key_hash=_KEY_HASH,
    status="active",
    expires_at=None,
)

_FAKE_TOOL = MagicMock(
    id=_TOOL_ID,
    tenant_id=_TENANT_ID,
    type="reconciliation",
    status="active",
)

_FAKE_EXECUTION = MagicMock(
    id=_EXECUTION_ID,
    tenant_id=_TENANT_ID,
    tool_id=_TOOL_ID,
    input_ref="idem_key_001",
    decision="pending",
    confidence=0.0,
    status="queued",
    duration_ms=None,
    error_message=None,
    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    tool=_FAKE_TOOL,
)


def _make_db_mock(*, existing_execution=None):
    db = AsyncMock()
    db.apikey.find_first = AsyncMock(return_value=_FAKE_API_KEY)
    db.tool.find_first = AsyncMock(return_value=_FAKE_TOOL)
    db.execution.find_first = AsyncMock(return_value=existing_execution)
    db.execution.create = AsyncMock(return_value=_FAKE_EXECUTION)
    db.apikey.update = AsyncMock(return_value=None)
    return db


def _make_pool_mock():
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock(return_value=None)
    return pool


# ---------------------------------------------------------------------------
# TOOL_TYPE_TO_EVENT coverage
# ---------------------------------------------------------------------------

ALL_13_TOOLS = [
    "reconciliation",
    "document_intelligence",
    "ai_accountant",
    "spend_control",
    "ar_collections",
    "risk_compliance",
    "treasury_cash",
    "revenue_recognition",
    "credit_underwriting",
    "tax_compliance",
    "financial_reporting",
    "payment_run",
    "budgeting",
]


class TestToolCoverage:
    def test_all_13_tools_in_map(self):
        missing = [t for t in ALL_13_TOOLS if t not in TOOL_TYPE_TO_EVENT]
        assert missing == [], f"Tools missing from TOOL_TYPE_TO_EVENT: {missing}"

    def test_expense_control_maps_to_handled_event(self):
        assert TOOL_TYPE_TO_EVENT["expense_control"] == "expense_control_run"

    def test_financial_reporting_maps_to_correct_event(self):
        assert TOOL_TYPE_TO_EVENT["financial_reporting"] == "financial_report_run"

    def test_payment_run_maps_to_correct_event(self):
        assert TOOL_TYPE_TO_EVENT["payment_run"] == "payment_run_requested"

    def test_budgeting_maps_to_correct_event(self):
        assert TOOL_TYPE_TO_EVENT["budgeting"] == "budget_check_run"


# ---------------------------------------------------------------------------
# POST /v1/execute tests
# ---------------------------------------------------------------------------

class TestPostExecute:

    def test_rejects_invalid_key_format(self):
        client = TestClient(app)
        response = client.post(
            "/execute",
            headers={"Authorization": "bad_key", "Idempotency-Key": "k1"},
            json={"tool": "reconciliation"},
        )
        assert response.status_code == 401

    def test_rejects_missing_idempotency_key(self):
        client = TestClient(app)
        response = client.post(
            "/execute",
            headers={"Authorization": _VALID_KEY},
            json={"tool": "reconciliation"},
        )
        assert response.status_code == 422

    def test_rejects_unknown_tool(self):
        db = _make_db_mock()
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.post(
                "/execute",
                headers=VALID_HEADERS,
                json={"tool": "nonexistent_tool"},
            )
        assert response.status_code == 400
        assert "Unknown tool type" in response.json()["detail"]

    def test_rejects_revoked_api_key(self):
        db = _make_db_mock()
        db.apikey.find_first = AsyncMock(return_value=None)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.post(
                "/execute",
                headers=VALID_HEADERS,
                json={"tool": "reconciliation"},
            )
        assert response.status_code == 401

    def test_queues_job_and_returns_execution_id(self):
        db = _make_db_mock()
        pool = _make_pool_mock()
        client = TestClient(app)
        with (
            patch("app.api.v1.execute.get_db", return_value=db),
            patch("app.api.v1.execute.get_queue_pool", AsyncMock(return_value=pool)),
        ):
            response = client.post(
                "/execute",
                headers=VALID_HEADERS,
                json={"tool": "reconciliation", "payload": {"period": "2026-01"}},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_id"] == _EXECUTION_ID
        assert data["status"] == "queued"
        assert data["decision"] == "pending"
        assert data["idempotent"] is False
        pool.enqueue_job.assert_called_once()

    def test_idempotent_returns_existing_execution(self):
        existing = MagicMock(
            id="exec_existing",
            status="completed",
            decision="auto_approved",
        )
        db = _make_db_mock(existing_execution=existing)
        pool = _make_pool_mock()
        client = TestClient(app)
        with (
            patch("app.api.v1.execute.get_db", return_value=db),
            patch("app.api.v1.execute.get_queue_pool", AsyncMock(return_value=pool)),
        ):
            response = client.post(
                "/execute",
                headers=VALID_HEADERS,
                json={"tool": "reconciliation"},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_id"] == "exec_existing"
        assert data["idempotent"] is True
        pool.enqueue_job.assert_not_called()

    def test_returns_404_when_tool_not_active(self):
        db = _make_db_mock()
        db.tool.find_first = AsyncMock(return_value=None)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.post(
                "/execute",
                headers=VALID_HEADERS,
                json={"tool": "budgeting"},
            )
        assert response.status_code == 404

    @pytest.mark.parametrize("tool_type", ALL_13_TOOLS)
    def test_all_13_tools_are_routable(self, tool_type: str):
        fake_tool = MagicMock(id=_TOOL_ID, tenant_id=_TENANT_ID, type=tool_type, status="active")
        db = _make_db_mock()
        db.tool.find_first = AsyncMock(return_value=fake_tool)
        pool = _make_pool_mock()
        client = TestClient(app)
        with (
            patch("app.api.v1.execute.get_db", return_value=db),
            patch("app.api.v1.execute.get_queue_pool", AsyncMock(return_value=pool)),
        ):
            response = client.post(
                "/execute",
                headers={"Authorization": _VALID_KEY, "Idempotency-Key": f"idem_{tool_type}"},
                json={"tool": tool_type},
            )
        assert response.status_code == 200, f"Tool '{tool_type}' returned {response.status_code}: {response.text}"
        data = response.json()["data"]
        assert data["status"] == "queued"
        # Verify the correct event type was enqueued
        call_kwargs = pool.enqueue_job.call_args
        assert call_kwargs.args[0] == "run_orchestrator_job"
        assert call_kwargs.kwargs["event_type"] == TOOL_TYPE_TO_EVENT[tool_type]


# ---------------------------------------------------------------------------
# GET /v1/execute/{execution_id} tests
# ---------------------------------------------------------------------------

class TestGetExecution:

    def _db_with_execution(self, *, with_audit=True):
        db = AsyncMock()
        db.apikey.find_first = AsyncMock(return_value=_FAKE_API_KEY)
        db.execution.find_first = AsyncMock(return_value=_FAKE_EXECUTION)
        audit = MagicMock(reasoning_trace_json={"decision": "auto_approved", "reasoning": "all checks passed"})
        db.auditlog.find_first = AsyncMock(return_value=audit if with_audit else None)
        return db

    def test_returns_execution_result(self):
        db = self._db_with_execution()
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.get(
                f"/execute/{_EXECUTION_ID}",
                headers={"Authorization": _VALID_KEY},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_id"] == _EXECUTION_ID
        assert data["status"] == "queued"
        assert data["decision"] == "pending"
        assert data["confidence"] == 0.0
        assert "reasoning_trace" in data
        assert "created_at" in data

    def test_returns_reasoning_trace_from_audit_log(self):
        db = self._db_with_execution(with_audit=True)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.get(
                f"/execute/{_EXECUTION_ID}",
                headers={"Authorization": _VALID_KEY},
            )
        data = response.json()["data"]
        assert data["reasoning_trace"] is not None
        assert data["reasoning_trace"]["reasoning"] == "all checks passed"

    def test_returns_null_trace_when_audit_not_yet_written(self):
        db = self._db_with_execution(with_audit=False)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.get(
                f"/execute/{_EXECUTION_ID}",
                headers={"Authorization": _VALID_KEY},
            )
        data = response.json()["data"]
        assert data["reasoning_trace"] is None

    def test_returns_404_for_unknown_execution(self):
        db = AsyncMock()
        db.apikey.find_first = AsyncMock(return_value=_FAKE_API_KEY)
        db.execution.find_first = AsyncMock(return_value=None)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.get(
                "/execute/does_not_exist",
                headers={"Authorization": _VALID_KEY},
            )
        assert response.status_code == 404

    def test_rejects_invalid_key(self):
        client = TestClient(app)
        response = client.get(
            f"/execute/{_EXECUTION_ID}",
            headers={"Authorization": "not_a_valid_key"},
        )
        assert response.status_code == 401

    def test_cannot_access_other_tenant_execution(self):
        db = AsyncMock()
        db.apikey.find_first = AsyncMock(return_value=_FAKE_API_KEY)
        # Execution scoped to a different tenant â€” DB returns None
        db.execution.find_first = AsyncMock(return_value=None)
        client = TestClient(app)
        with patch("app.api.v1.execute.get_db", return_value=db):
            response = client.get(
                "/execute/other_tenant_exec",
                headers={"Authorization": _VALID_KEY},
            )
        assert response.status_code == 404
