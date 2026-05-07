from app.privacy_scrub import redact_sensitive, scrub_sensitive_text


def test_scrub_email_phone_url():
    t = "Reach me at a@b.com or +1 212-555-9999 see https://evil.test/x"
    out = scrub_sensitive_text(t)
    assert "a@b.com" not in out
    assert "https://evil.test" not in out
    assert "[email]" in out


def test_scrub_bearer_jwt_db_url_keys():
    t = "Authorization Bearer abcdefghijklmnopqrs OPENAI_API_KEY=sk-12345678901234567890 postgresql://u:pw@host:5432/db"
    out = scrub_sensitive_text(t)
    assert "sk-" not in out
    assert "postgresql://" not in out


def test_scrub_ip_ssn_long_id():
    t = "host 192.168.1.1 ssn 123-45-6789 id 123456789012"
    out = scrub_sensitive_text(t)
    assert "192.168.1.1" not in out
    assert "123-45-6789" not in out


def test_redact_sensitive_nested_no_mutation():
    payload = {"nested": {"note": "x@y.com"}, "ok": "keep"}
    original = payload["nested"]["note"]
    out = redact_sensitive(payload)
    assert payload["nested"]["note"] == original
    assert "x@y.com" not in out["nested"]["note"]
    assert out["ok"] == "keep"
