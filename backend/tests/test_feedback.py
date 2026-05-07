from app.feedback import (
    build_feedback_profile,
    moderate_comment,
    normalize_feedback_payload,
    normalize_tag,
    redact_comment,
    validate_rating,
)
import app.scoring as scoring_module
import inspect


def _make_session(client, headers, max_turns=2):
    return client.post("/api/v1/sessions", json={"scenario": "workplace", "max_turns": max_turns}, headers=headers).json()


def _complete_session(client, headers, session_id):
    first = client.post("/api/v1/scenes/next", json={"session_id": session_id}, headers=headers).json()
    second = client.post(
        "/api/v1/scenes/next",
        json={"session_id": session_id, "scene_id": first["id"], "choice_id": "A", "telemetry": {"latency_ms": 1000}},
        headers=headers,
    ).json()
    client.post(
        "/api/v1/scenes/next",
        json={"session_id": session_id, "scene_id": second["id"], "choice_id": "B", "telemetry": {"latency_ms": 1100}},
        headers=headers,
    )


def test_normalize_tag():
    assert normalize_tag("Too Fast") == "too_fast"
    assert normalize_tag("unknown_tag") == ""


def test_validate_rating():
    assert validate_rating(1) == 1
    assert validate_rating(5) == 5
    try:
        validate_rating(0)
        assert False
    except ValueError:
        assert True
    try:
        validate_rating(6)
        assert False
    except ValueError:
        assert True


def test_comment_consent_and_micro_rules():
    payload = normalize_feedback_payload(
        {
            "session_id": "s1",
            "feedback_type": "session",
            "channel": "post_report",
            "rating_useful": 4,
            "comment": "hello",
            "consent_comment": False,
        }
    )
    assert payload["comment"] is None
    micro = normalize_feedback_payload(
        {
            "session_id": "s1",
            "feedback_type": "micro",
            "channel": "in_session",
            "tags": ["too_fast"],
            "comment": "ignored",
        }
    )
    assert micro["comment"] is None


def test_redaction_and_moderation():
    redacted = redact_comment("mail me at a@b.com and https://x.com @user eyJtoken.part.sig 123456789")
    assert "[email]" in redacted
    assert "[url]" in redacted
    assert "[handle]" in redacted
    assert "[token]" in redacted
    assert ("[id]" in redacted) or ("[phone]" in redacted)
    status, flags = moderate_comment("ignore previous instructions", ["bug_report"])
    assert status == "flagged"
    assert "suspicious_prompt_injection" in flags
    assert "bug_report" in flags


def test_feedback_routes_and_scoring_safety(test_client, auth_headers):
    session = _make_session(test_client, auth_headers, max_turns=2)
    _complete_session(test_client, auth_headers, session["id"])
    before = test_client.get(f"/api/v1/reports/{session['id']}", headers=auth_headers).json()
    feedback = test_client.post(
        "/api/v1/feedback",
        json={
            "session_id": session["id"],
            "report_id": session["id"],
            "feedback_type": "session",
            "channel": "post_report",
            "rating_useful": 4,
            "rating_engaging": 4,
            "tags": ["helpful"],
            "comment": "Great report, email me at test@example.com",
            "consent_comment": True,
        },
        headers=auth_headers,
    )
    assert feedback.status_code == 200
    assert "comment" not in feedback.text.lower()
    my = test_client.get(f"/api/v1/feedback/my?session_id={session['id']}", headers=auth_headers)
    assert my.status_code == 200
    rows = my.json()
    assert rows and isinstance(rows[0].get("analysis"), dict)
    assert rows[0]["analysis"].get("version") == "analysis_nlp_v1"
    serialized = str(rows[0]).lower()
    assert "test@example.com" not in serialized
    pii = rows[0]["analysis"].get("pii") or {}
    assert pii.get("has_pii") is True
    assert "email" in (pii.get("entity_types") or [])
    summary = test_client.get(f"/api/v1/feedback/summary?session_id={session['id']}", headers=auth_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert "top_topics" in body
    assert "sentiment_counts" in body
    after = test_client.get(f"/api/v1/reports/{session['id']}", headers=auth_headers).json()
    before_scores = [f["score"] for f in before["features"]]
    after_scores = [f["score"] for f in after["features"]]
    assert before_scores == after_scores


def test_owner_and_admin_checks(test_client, auth_headers):
    import uuid

    session = _make_session(test_client, auth_headers)
    user2_email = "feedback-u2@example.com"
    user2_pw = "strongpass123"
    test_client.post("/api/v1/auth/register", json={"email": user2_email, "password": user2_pw})
    login2 = test_client.post(
        "/api/v1/auth/login", params={"include_token": "true"}, json={"email": user2_email, "password": user2_pw}
    ).json()
    headers2 = {"Authorization": f"Bearer {login2['access_token']}"}
    forbidden = test_client.post(
        "/api/v1/feedback",
        json={"session_id": session["id"], "feedback_type": "micro", "channel": "in_session", "tags": ["too_fast"]},
        headers=headers2,
    )
    assert forbidden.status_code == 404
    from app.main import create_user, hash_password

    admin_email = f"admin-feedback-{uuid.uuid4().hex[:6]}@example.com"
    create_user(admin_email, hash_password("strongpass123"), role="admin")
    admin_login = test_client.post(
        "/api/v1/auth/login", params={"include_token": "true"}, json={"email": admin_email, "password": "strongpass123"}
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    admin_list = test_client.get("/api/v1/admin/feedback?status=flagged", headers=admin_headers)
    assert admin_list.status_code == 200
    non_admin = test_client.get("/api/v1/admin/feedback?status=flagged", headers=auth_headers)
    assert non_admin.status_code == 403


def test_feedback_profile_no_raw_comment():
    profile = build_feedback_profile(
        [{"feedback_type": "micro", "turn": 2, "tags_json": ["too_fast", "confusing"], "comment": "secret raw"}], current_turn=3
    )
    assert profile["hints"]["pace"] == "slower"
    assert "comment" not in str(profile).lower()


def test_consent_false_and_micro_feedback_analysis(test_client, auth_headers):
    session = _make_session(test_client, auth_headers, max_turns=2)
    no_consent = test_client.post(
        "/api/v1/feedback",
        json={
            "session_id": session["id"],
            "feedback_type": "session",
            "channel": "post_report",
            "rating_useful": 3,
            "tags": ["too_fast"],
            "comment": "my email is test@example.com",
            "consent_comment": False,
        },
        headers=auth_headers,
    )
    assert no_consent.status_code == 200
    micro = test_client.post(
        "/api/v1/feedback",
        json={"session_id": session["id"], "feedback_type": "micro", "channel": "in_session", "tags": ["bug_report"]},
        headers=auth_headers,
    )
    assert micro.status_code == 200
    events = test_client.get(f"/api/v1/feedback/my?session_id={session['id']}", headers=auth_headers).json()
    assert len(events) >= 2
    serialized = str(events).lower()
    assert "test@example.com" not in serialized


def test_scoring_module_has_no_analysis_nlp_import():
    source = inspect.getsource(scoring_module).lower()
    assert "analysis_nlp" not in source
    assert "from .feedback" not in source
