import uuid


def _session(client, headers):
    return client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 5}, headers=headers).json()


def test_session_detail_and_state_owner(test_client, auth_headers):
    s = _session(test_client, auth_headers)
    d = test_client.get(f"/api/v1/sessions/{s['id']}", headers=auth_headers)
    assert d.status_code == 200
    detail = d.json()
    assert detail["id"] == s["id"]
    assert detail["current_turn"] == 0
    assert detail["status"] == "active"

    st = test_client.get(f"/api/v1/sessions/{s['id']}/state", headers=auth_headers)
    assert st.status_code == 200
    body = st.json()
    assert body["can_resume"] is True
    assert body["choices_count"] == 0
    assert body["report_ready"] is False
    assert body["latest_scene"] is None


def test_session_state_forbidden_for_other_user(test_client, auth_headers):
    s = _session(test_client, auth_headers)
    other_email = f"other-{uuid.uuid4().hex[:6]}@example.com"
    test_client.post("/api/v1/auth/register", json={"email": other_email, "password": "strongpass123"})
    other = test_client.post(
        "/api/v1/auth/login", params={"include_token": "true"}, json={"email": other_email, "password": "strongpass123"}
    ).json()
    bad = test_client.get(f"/api/v1/sessions/{s['id']}/state", headers={"Authorization": f"Bearer {other['access_token']}"})
    assert bad.status_code == 404


def test_session_state_report_ready_when_complete(test_client, auth_headers):
    s = test_client.post(
        "/api/v1/sessions", json={"scenario": "workplace", "max_turns": 1}, headers=auth_headers
    ).json()
    first = test_client.post("/api/v1/scenes/next", json={"session_id": s["id"]}, headers=auth_headers).json()
    r2 = test_client.post(
        "/api/v1/scenes/next",
        json={
            "session_id": s["id"],
            "scene_id": first["id"],
            "choice_id": "A",
            "telemetry": {"latency_ms": 100},
        },
        headers=auth_headers,
    )
    assert r2.status_code == 410
    st = test_client.get(f"/api/v1/sessions/{s['id']}/state", headers=auth_headers)
    assert st.status_code == 200
    body = st.json()
    assert body["session"]["status"] == "complete"
    assert body["report_ready"] is True
    assert body["can_resume"] is False
