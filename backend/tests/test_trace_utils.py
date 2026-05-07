from app.trace_utils import canonical_json, parse_traceparent, redact_sensitive, safe_trace_json, sha256_json


def test_canonical_json_stable():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_sha256_json_stable():
    assert sha256_json({"a": 1}) == sha256_json({"a": 1})


def test_parse_traceparent_valid():
    out = parse_traceparent("00-0123456789abcdef0123456789abcdef-0123456789abcdef-01")
    assert out["trace_id"] == "0123456789abcdef0123456789abcdef"


def test_parse_traceparent_invalid_generates_ids():
    out = parse_traceparent("bad")
    assert len(out["trace_id"]) == 32
    assert out["parent_trace_id"] is None


def test_redact_sensitive_fields():
    obj = {"password": "x", "token": "y", "email": "a@b.com", "nested": {"api_key": "z"}}
    red = redact_sensitive(obj)
    assert red["password"] == "[REDACTED]"
    assert red["nested"]["api_key"] == "[REDACTED]"


def test_safe_trace_json_truncates():
    data = {"note": "x" * 3000, "authorization": "secret"}
    out = safe_trace_json(data)
    assert out["note"].endswith("...[truncated]")
    assert "authorization" not in out
