import uuid

def test_login_default_no_access_token_cookie_type(test_client):
    email = f"authout-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    r = test_client.post("/api/v1/auth/login", json={"email": email, "password": "strongpass123"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("token_type") == "cookie"
    assert body.get("access_token") in (None, "")
    assert "password_hash" not in str(body).lower()
    me = test_client.get("/api/v1/me")
    assert me.status_code == 200


def test_include_token_query_returns_bearer_body(test_client):
    email = f"tokq-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    r = test_client.post("/api/v1/auth/login", params={"include_token": "true"}, json={"email": email, "password": "strongpass123"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("token_type") == "bearer"
    assert body.get("access_token")
    assert len(body["access_token"]) > 10


def test_return_bearer_header_override(test_client):
    email = f"tokh-{uuid.uuid4().hex[:8]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "strongpass123"})
    r = test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strongpass123"},
        headers={"X-Return-Bearer-Token": "true"},
    )
    assert r.status_code == 200
    assert r.json().get("access_token")


def test_bearer_still_works_for_me(test_client):
    email = f"mebear-{uuid.uuid4().hex[:8]}@example.com"
    reg = test_client.post(
        "/api/v1/auth/register", params={"include_token": "true"}, json={"email": email, "password": "strongpass123"}
    )
    token = reg.json()["access_token"]
    me = test_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
