import uuid


def test_login_invalid_generic_error(test_client):
    r = test_client.post("/api/v1/auth/login", json={"email": "none@example.com", "password": "badpass123"})
    assert r.status_code == 401
    assert r.json().get("detail") == "invalid_credentials"


def test_register_login_and_me(test_client):
    email = f"authuser-{uuid.uuid4().hex[:8]}@example.com"
    password = "strongpass123"
    reg = test_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 200
    body = reg.json()
    assert "password_hash" not in str(body).lower()
    token = body["access_token"]
    me = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_protected_route_requires_token(test_client):
    r = test_client.get("/api/v1/my-sessions")
    assert r.status_code in (401, 403)
