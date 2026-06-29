"""
API stub endpoint tests.
Verifies correct response shape for the three stub routes:
  POST /v1/reconcile
  POST /v1/fraud/score
  POST /v1/parse/contract

Auth is bypassed by overriding the require_auth dependency.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import require_auth, get_current_user, CurrentUser

FAKE_PAYLOAD = {"sub": "user_test", "email": "test@example.com"}
FAKE_USER = CurrentUser(
    user_id="user_test",
    org_id="org_test",
    tenant_id="tenant_test",
    email="test@example.com",
    role="owner",
)


def _make_client() -> TestClient:
    app.dependency_overrides[require_auth] = lambda: FAKE_PAYLOAD
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def teardown_module(module: object) -> None:
    app.dependency_overrides.clear()


class TestReconcileStub:

    def test_returns_200_with_correct_shape(self):
        client = _make_client()
        response = client.post(
            "/reconcile",
            json={"source_dataset": [], "target_dataset": []},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert "trace_id" in body
        assert "timestamp" in body
        data = body["data"]
        assert "matched" in data
        assert "unmatched" in data
        assert "flagged" in data
        assert "confidence" in data

    def test_matched_is_list(self):
        client = _make_client()
        response = client.post(
            "/reconcile",
            json={"source_dataset": [], "target_dataset": []},
        )
        data = response.json()["data"]
        assert isinstance(data["matched"], list)
        assert isinstance(data["unmatched"], list)
        assert isinstance(data["flagged"], list)

    def test_confidence_is_float(self):
        client = _make_client()
        response = client.post(
            "/reconcile",
            json={"source_dataset": [], "target_dataset": []},
        )
        data = response.json()["data"]
        assert isinstance(data["confidence"], float)

    def test_requires_auth(self):
        app.dependency_overrides.clear()
        bare_client = TestClient(app)
        response = bare_client.post(
            "/reconcile",
            json={"source_dataset": [], "target_dataset": []},
        )
        assert response.status_code in (401, 403)
        app.dependency_overrides[require_auth] = lambda: FAKE_PAYLOAD


class TestFraudScoreStub:

    def test_returns_200_with_correct_shape(self):
        client = _make_client()
        response = client.post(
            "/fraud/score",
            json={
                "transaction_id": "txn_001",
                "amount_minor": 5000,
                "currency": "GBP",
                "counterparty": "Acme Corp",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert "trace_id" in body
        assert "timestamp" in body
        data = body["data"]
        assert "risk_score" in data
        assert "risk_level" in data
        assert "signals" in data
        assert "action" in data

    def test_signals_is_list(self):
        client = _make_client()
        response = client.post(
            "/fraud/score",
            json={
                "transaction_id": "txn_002",
                "amount_minor": 1000,
                "currency": "USD",
                "counterparty": "Vendor",
            },
        )
        data = response.json()["data"]
        assert isinstance(data["signals"], list)

    def test_risk_score_is_float(self):
        client = _make_client()
        response = client.post(
            "/fraud/score",
            json={
                "transaction_id": "txn_003",
                "amount_minor": 100,
                "currency": "EUR",
                "counterparty": "Test",
            },
        )
        data = response.json()["data"]
        assert isinstance(data["risk_score"], float)

    def test_requires_auth(self):
        app.dependency_overrides.clear()
        bare_client = TestClient(app)
        response = bare_client.post(
            "/fraud/score",
            json={
                "transaction_id": "txn_noauth",
                "amount_minor": 100,
                "currency": "GBP",
                "counterparty": "X",
            },
        )
        assert response.status_code in (401, 403)
        app.dependency_overrides[require_auth] = lambda: FAKE_PAYLOAD

    def test_accepts_optional_metadata(self):
        client = _make_client()
        response = client.post(
            "/fraud/score",
            json={
                "transaction_id": "txn_004",
                "amount_minor": 250,
                "currency": "GBP",
                "counterparty": "Vendor",
                "metadata": {"channel": "online", "device": "mobile"},
            },
        )
        assert response.status_code == 200


class TestParseContractStub:

    def test_returns_200_with_correct_shape(self):
        client = _make_client()
        response = client.post(
            "/parse/contract",
            json={"file_bytes_b64": "dGVzdA==", "content_type": "application/pdf"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["error"] is None
        assert "trace_id" in body
        assert "timestamp" in body
        data = body["data"]
        assert "counterparty" in data
        assert "confidence" in data

    def test_confidence_is_float(self):
        client = _make_client()
        response = client.post(
            "/parse/contract",
            json={"file_bytes_b64": "dGVzdA=="},
        )
        data = response.json()["data"]
        assert isinstance(data["confidence"], float)

    def test_obligations_is_list(self):
        client = _make_client()
        response = client.post(
            "/parse/contract",
            json={"file_bytes_b64": "dGVzdA=="},
        )
        data = response.json()["data"]
        assert isinstance(data["obligations"], list)
        assert isinstance(data["amounts"], list)

    def test_requires_auth(self):
        app.dependency_overrides.clear()
        bare_client = TestClient(app)
        response = bare_client.post(
            "/parse/contract",
            json={"file_bytes_b64": "dGVzdA=="},
        )
        assert response.status_code in (401, 403)
        app.dependency_overrides[require_auth] = lambda: FAKE_PAYLOAD

    def test_content_type_defaults_to_pdf(self):
        client = _make_client()
        response = client.post(
            "/parse/contract",
            json={"file_bytes_b64": "dGVzdA=="},
        )
        assert response.status_code == 200
