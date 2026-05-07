from app.store import list_feedback_for_session


def _session(client, headers):
    return client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 3}, headers=headers).json()


def _first_scene(client, headers, session_id):
    return client.post("/api/v1/scenes/next", json={"session_id": session_id}, headers=headers).json()


def test_micro_feedback_duplicate_same_turn(test_client, auth_headers):
    s = _session(test_client, auth_headers)
    scene = _first_scene(test_client, auth_headers, s["id"])
    turn = scene["turn"]
    payload = {
        "session_id": s["id"],
        "scene_id": scene["id"],
        "turn": turn,
        "feedback_type": "micro",
        "channel": "in_session",
        "tags": ["too_fast"],
    }
    a = test_client.post("/api/v1/feedback", json=payload, headers=auth_headers)
    assert a.status_code == 200
    assert a.json().get("status") == "accepted"
    b = test_client.post("/api/v1/feedback", json=payload, headers=auth_headers)
    assert b.status_code == 200
    body = b.json()
    assert body.get("status") == "duplicate_ignored"
    assert body.get("existing_id") == a.json().get("id")
    rows = list_feedback_for_session(s["id"])
    assert sum(1 for r in rows if r.get("feedback_type") == "micro") == 1


def test_micro_feedback_different_turn_allowed(test_client, auth_headers):
    s = _session(test_client, auth_headers)
    sc1 = _first_scene(test_client, auth_headers, s["id"])
    test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": s["id"], "scene_id": sc1["id"], "choice_id": "A", "telemetry": {"latency_ms": 100}},
        headers=auth_headers,
    )
    sc2 = test_client.post("/api/v1/scenes/next", json={"session_id": s["id"]}, headers=auth_headers).json()
    for sc, turn in ((sc1, sc1["turn"]), (sc2, sc2["turn"])):
        r = test_client.post(
            "/api/v1/feedback",
            json={
                "session_id": s["id"],
                "scene_id": sc["id"],
                "turn": turn,
                "feedback_type": "micro",
                "channel": "in_session",
                "tags": ["clear"],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json().get("status") == "accepted"


def test_session_feedback_still_accepted_after_micro(test_client, auth_headers):
    s = _session(test_client, auth_headers)
    sc1 = _first_scene(test_client, auth_headers, s["id"])
    test_client.post(
        "/api/v1/feedback",
        json={
            "session_id": s["id"],
            "scene_id": sc1["id"],
            "turn": sc1["turn"],
            "feedback_type": "micro",
            "channel": "in_session",
            "tags": ["too_fast"],
        },
        headers=auth_headers,
    )
    fr = test_client.post(
        "/api/v1/feedback",
        json={
            "session_id": s["id"],
            "feedback_type": "session",
            "channel": "post_report",
            "rating_useful": 4,
            "tags": ["helpful"],
        },
        headers=auth_headers,
    )
    assert fr.status_code == 200
    assert fr.json().get("status") == "accepted"
