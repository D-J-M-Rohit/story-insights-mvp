def test_security_headers_present_on_health(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
    assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert "connect-src 'self'" in (response.headers.get("Content-Security-Policy") or "")
