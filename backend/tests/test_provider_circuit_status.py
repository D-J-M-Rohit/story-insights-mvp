from app.circuit_breaker import get_provider_circuit_breaker
from app.config import settings
from app.store import create_user, get_user_by_email
from app.auth import create_access_token, hash_password


def _admin_headers():
    email = "admin-circuit@example.com"
    user = get_user_by_email(email)
    if not user:
        user = create_user(email, hash_password("strongpass123"), role="admin")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def test_circuit_status_requires_auth(test_client):
    test_client.cookies.clear()
    response = test_client.get("/api/v1/provider/circuit-status")
    assert response.status_code == 401


def test_circuit_status_requires_admin(test_client, auth_headers):
    response = test_client.get("/api/v1/provider/circuit-status", headers=auth_headers)
    assert response.status_code == 403


def test_circuit_status_returns_shape_and_no_secrets(test_client):
    breaker = get_provider_circuit_breaker(settings)
    breaker.reset()
    response = test_client.get("/api/v1/provider/circuit-status", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "circuits" in body
    assert isinstance(body["circuits"], list)
    serialized = str(body).lower()
    for forbidden in ("api_key", "authorization", "token", "prompt", "password"):
        assert forbidden not in serialized


def test_circuit_status_reflects_failure_state(test_client):
    breaker = get_provider_circuit_breaker(settings)
    breaker.reset()
    for _ in range(int(settings.PROVIDER_CIRCUIT_FAILURE_THRESHOLD)):
        breaker.record_failure("openai", "gpt-4.1-mini", "forced_test_failure")
    response = test_client.get("/api/v1/provider/circuit-status", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    circuit = next((c for c in body["circuits"] if c["provider"] == "openai"), None)
    assert circuit is not None
    assert circuit["state"] in {"open", "half_open", "closed"}
    assert "failure_count" in circuit
