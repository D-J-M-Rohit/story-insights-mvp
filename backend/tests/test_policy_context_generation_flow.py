import pytest


def test_policy_context_generation_flow_if_available(test_client, auth_headers):
    session = test_client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": 2}, headers=auth_headers).json()
    scene = test_client.post("/api/v1/scenes/next", json={"session_id": session["id"]}, headers=auth_headers)
    assert scene.status_code == 200
    s = scene.json()
    assert s.get("scene_metadata", {}).get("target_construct")
    traces = test_client.get(f"/api/v1/policy-traces/{session['id']}", headers=auth_headers)
    assert traces.status_code == 200
    ctx = test_client.get(f"/api/v1/context-traces/{session['id']}", headers=auth_headers)
    assert ctx.status_code == 200
    debug = test_client.get(f"/api/v1/debug/sessions/{session['id']}/traces?kind=generation", headers=auth_headers)
    assert debug.status_code == 200


@pytest.mark.skipif(False, reason="rate limiting module present")
def test_placeholder():
    assert True
