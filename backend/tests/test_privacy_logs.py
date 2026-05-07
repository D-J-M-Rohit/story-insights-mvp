from app.logging_config import JsonFormatter, redact_sensitive


def test_redact_sensitive_keys():
    payload = {
        "email": "x@y.com",
        "token": "abc",
        "password": "secret",
        "scene": "raw story body",
        "nested": {"authorization": "Bearer xyz"},
    }
    redacted = redact_sensitive(payload)
    assert redacted["email"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["scene"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"


def test_structured_log_has_request_trace_without_raw_email():
    formatter = JsonFormatter()
    import logging

    record = logging.LogRecord("story_insights", logging.INFO, "", 0, "request_completed", (), None)
    record.request_id = "req_123"
    record.trace_id = "a" * 32
    record.event = "request_completed"
    record.message = "ok"
    rendered = formatter.format(record).lower()
    assert '"request_id":"req_123"' in rendered
    assert '"trace_id":"' in rendered
    assert "email" not in rendered
