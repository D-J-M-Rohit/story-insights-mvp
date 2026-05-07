import uuid

from app.auth import create_access_token
from app.config import settings
from app.store import get_user_by_email


def test_register_login_response_no_bearer_body_by_default(test_client):
    email = f"cookie-reg-{uuid.uuid4().hex[:8]}@example.com"
    response = test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    assert response.status_code == 200
    assert "password_hash" not in str(response.json()).lower()
    body = response.json()
    assert body.get("access_token") in (None, "")
    assert body.get("token_type") == "cookie"
    cookie_header = response.headers.get("set-cookie", "")
    assert settings.AUTH_COOKIE_NAME in cookie_header
    assert "HttpOnly" in cookie_header


def test_login_sets_cookie_and_me_works_with_cookie_only(test_client):
    email = f"cookie-login-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    response = test_client.post("/api/v1/auth/login", json={"email": email, "password": "strongpass123"})
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert settings.AUTH_COOKIE_NAME in cookie_header
    assert "HttpOnly" in cookie_header
    me = test_client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_me_still_works_with_bearer_token(test_client):
    email = f"bearer-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    user = get_user_by_email(email)
    token = create_access_token(user)
    me = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_logout_clears_cookie_and_invalid_cookie_rejected(test_client):
    email = f"logout-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    logged_in = test_client.post("/api/v1/auth/login", json={"email": email, "password": "strongpass123"})
    assert logged_in.status_code == 200
    logged_out = test_client.post("/api/v1/auth/logout")
    assert logged_out.status_code == 200
    assert logged_out.json() == {"ok": True}
    clear_cookie_header = logged_out.headers.get("set-cookie", "")
    assert settings.AUTH_COOKIE_NAME in clear_cookie_header
    test_client.cookies.clear()
    test_client.cookies.set(settings.AUTH_COOKIE_NAME, "not-a-real-token")
    me = test_client.get("/api/v1/me")
    assert me.status_code == 401
