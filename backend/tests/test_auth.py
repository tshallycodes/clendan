import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.core.security as security_module

client = TestClient(app)

PROTECTED_ROUTES = [
    ("GET", "/v1/tenants/me"),
    ("POST", "/v1/onboarding"),
]


def _clear_jwks_cache():
    """Clear the module-level JWKS cache so tests don't share state."""
    security_module._jwks_cache = None


class TestAuthProtection:
    """Protected routes must reject requests with missing or invalid tokens."""

    def setup_method(self):
        _clear_jwks_cache()

    @pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
    def test_requires_auth_no_token(self, method: str, path: str):
        """
        Missing Authorization header.

        FastAPI's HTTPBearer raises 403 (Forbidden) when the Authorization
        header is absent entirely — this is the FastAPI default for a missing
        bearer credential, distinct from an invalid one.  Both 401 and 403
        are acceptable rejections; what matters is that the route is not open.
        """
        response = client.request(method, path, json={})
        assert response.status_code in (401, 403), (
            f"{method} {path} should return 401 or 403 without auth, "
            f"got {response.status_code}"
        )

    @pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
    def test_requires_auth_invalid_token(self, method: str, path: str):
        """
        Malformed / unsigned JWT must be rejected with 401.

        require_auth catches JWTError / JWKError / httpx.HTTPError and raises
        HTTP 401, so an invalid token always produces 401 regardless of whether
        the JWKS fetch itself fails (which it will in the test environment
        because clerk_frontend_api is empty).
        """
        response = client.request(
            method,
            path,
            json={},
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert response.status_code == 401, (
            f"{method} {path} should return 401 with invalid token, "
            f"got {response.status_code}"
        )

    def test_health_is_public(self):
        """Health endpoint must remain public — no auth required."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_ready_is_public(self):
        """Ready endpoint must remain public — no auth required."""
        response = client.get("/ready")
        assert response.status_code == 200

    def test_invalid_token_response_shape(self):
        """401 response body must follow FastAPI's standard error shape."""
        response = client.get(
            "/v1/tenants/me",
            headers={"Authorization": "Bearer invalid"},
        )
        assert response.status_code == 401
        body = response.json()
        # FastAPI wraps HTTPException detail in {"detail": "..."}
        assert "detail" in body, (
            f"Expected 'detail' key in 401 response body, got: {body}"
        )
        assert body["detail"], "detail must not be empty"
