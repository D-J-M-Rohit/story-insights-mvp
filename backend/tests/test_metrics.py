from app.metrics import _route_label


def test_route_label_normalization():
    assert _route_label("/api/v1/reports/abc123") == "/api/v1/reports/{session_id}"
    assert _route_label("/api/v1/reports/abc123/pdf") == "/api/v1/reports/{session_id}/pdf"
    assert _route_label("/health") == "/health"


def test_metrics_endpoint_privacy(test_client):
    test_client.get("/health")
    r = test_client.get("/metrics")
    assert r.status_code == 200
    text = r.text.lower()
    assert "story_insights_http_requests_total" in text
    assert "authorization" not in text
    assert "password" not in text
