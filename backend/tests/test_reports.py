def _new_session_and_complete(test_client, headers):
    session = test_client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 2}, headers=headers).json()
    first = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=headers).json()
    second = test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": first["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=headers,
    )
    assert second.status_code == 200
    done = test_client.post(
        "/api/v1/scenes/next",
        json={"session_id": session["id"], "scene_id": second.json()["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=headers,
    )
    assert done.status_code == 410
    return session["id"]


def test_report_contains_features_and_evidence(test_client, auth_headers):
    session_id = _new_session_and_complete(test_client, auth_headers)
    report = test_client.get(f"/api/v1/reports/{session_id}", headers=auth_headers)
    assert report.status_code == 200
    body = report.json()
    assert len(body.get("features", [])) == 10
    assert "interpretation" in body
    assert "evidence_cards" in body


def test_pdf_route_if_available(test_client, auth_headers):
    session_id = _new_session_and_complete(test_client, auth_headers)
    pdf = test_client.get(f"/api/v1/reports/{session_id}/pdf", headers=auth_headers)
    assert pdf.status_code == 200
    assert "application/pdf" in pdf.headers.get("content-type", "")
