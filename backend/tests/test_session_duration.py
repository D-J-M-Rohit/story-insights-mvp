def _new_session_and_complete(test_client, headers):
    session = test_client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 2}, headers=headers).json()
    first = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=headers).json()
    second = test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": first["id"], "choice_id": "A", "telemetry": {"latency_ms": 800}},
        headers=headers,
    )
    assert second.status_code == 200
    done = test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": second.json()["id"], "choice_id": "B", "telemetry": {"latency_ms": 900}},
        headers=headers,
    )
    assert done.status_code == 410
    return session["id"]


def test_report_includes_session_duration_metadata(test_client, auth_headers):
    session_id = _new_session_and_complete(test_client, auth_headers)
    report = test_client.get(f"/api/v1/reports/{session_id}", headers=auth_headers)
    assert report.status_code == 200
    body = report.json()
    assert body.get("started_at") is not None
    assert body.get("completed_at") is not None
    assert isinstance(body.get("duration_ms"), int)
    assert body.get("duration_ms") >= 0
