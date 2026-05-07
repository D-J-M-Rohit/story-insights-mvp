def test_health_ok(test_client):
    r = test_client.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_metrics_and_request_id(test_client):
    r = test_client.get("/metrics")
    assert r.status_code == 200
    assert "story_insights_http_requests_total" in r.text
    assert r.headers.get("X-Request-ID", "").startswith("req_")
