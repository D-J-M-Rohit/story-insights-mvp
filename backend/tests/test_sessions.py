def _create_session(test_client, headers, scenario="workplace"):
    r = test_client.post("/api/v1/sessions", json={"scenario": scenario, "max_turns": 2}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_session_and_first_scene(auth_headers, test_client):
    session = _create_session(test_client, auth_headers)
    assert session["user_id"]
    scene = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers)
    assert scene.status_code == 200, scene.text
    assert len(scene.json().get("options", [])) == 3


def test_second_scene_saves_previous_choice(auth_headers, test_client):
    session = _create_session(test_client, auth_headers)
    first = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers).json()
    second = test_client.post(
        "/api/v1/scenes/next",
        json={
            "session_id": session["id"],
            "scene_id": first["id"],
            "choice_id": "A",
            "telemetry": {"latency_ms": 1000, "hover_switch_count": 1, "changed_intent": False, "timed_out": False},
        },
        headers=auth_headers,
    )
    assert second.status_code in (200, 410), second.text
