from app.scoring import score_session


def _session():
    return {"id": "s1", "scenario": "workplace", "max_turns": 5}


def test_score_session_empty_choices():
    report = score_session(_session(), [])
    assert len(report["features"]) == 10
    assert all(0 <= f["score"] <= 100 for f in report["features"])


def test_score_session_deterministic():
    choices = [
        {"id": "c1", "traits": {"risk": 0.9, "social": 0.2, "empathy": 0.3, "decisiveness": 0.8, "emotional_regulation": 0.4}},
        {"id": "c2", "traits": {"risk": 0.1, "social": 0.7, "empathy": 0.8, "decisiveness": 0.4, "emotional_regulation": 0.6}},
    ]
    a = score_session(_session(), choices)
    b = score_session(_session(), choices)
    assert a["features"] == b["features"]
