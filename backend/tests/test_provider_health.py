from app.provider_health import ProviderHealthTracker


def test_provider_health_status_transitions():
    tracker = ProviderHealthTracker(max_events=10)
    assert tracker.snapshot()["status"] == "unknown"
    for _ in range(3):
        tracker.record_event("mock", "mock", "ok", 100)
    assert tracker.snapshot()["status"] == "healthy"
    for _ in range(2):
        tracker.record_event("openai", "gpt", "fallback", 4000, fallback_reason="provider_exception")
    assert tracker.snapshot()["status"] in {"degraded", "unhealthy"}
    tracker.reset()
    for _ in range(6):
        tracker.record_event("openai", "gpt", "error", 5000, error_type="timeout")
    assert tracker.snapshot()["status"] == "unhealthy"


def test_provider_status_endpoint(test_client, auth_headers):
    r = test_client.get("/api/v1/provider/status", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "active_provider" in data
    assert "status" in data
    assert "api_key" not in str(data).lower()
