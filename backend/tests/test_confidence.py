from app.confidence import attach_confidence_to_feature, attach_confidence_to_report, confidence_band


def _choices(good=True, n=5):
    out = []
    for i in range(n):
        out.append(
            {
                "id": f"c{i}",
                "traits": {"risk": 0.6, "social": 0.5, "empathy": 0.5, "decisiveness": 0.5, "emotional_regulation": 0.5},
                "telemetry": {"latency_ms": 15000 if good else None, "latency_ratio": 0.4, "timed_out": False, "hover_switch_count": 2, "changed_intent": False},
                "scene_metadata": {"time_pressure": 0.6},
                "time_limit_sec": 45,
            }
        )
    return out


def test_confidence_band_bounds():
    c = confidence_band(70, evidence_count=5, completed_count=5, expected_count=5, telemetry_penalty=2)
    assert 0 <= c["confidence_low"] <= 100
    assert 0 <= c["confidence_high"] <= 100


def test_margin_decreases_with_more_evidence():
    low = confidence_band(70, 2, 2, 5, 0)["confidence_margin"]
    high = confidence_band(70, 10, 10, 10, 0)["confidence_margin"]
    assert high < low


def test_missing_telemetry_increases_margin():
    a = confidence_band(70, 5, 5, 5, 0)["confidence_margin"]
    b = confidence_band(70, 5, 5, 5, 12)["confidence_margin"]
    assert b > a


def test_low_evidence_insufficient():
    c = confidence_band(60, evidence_count=2, completed_count=2, expected_count=5, telemetry_penalty=0)
    assert c["confidence_level"] == "insufficient_evidence"


def test_directional_with_good_data():
    f = {"key": "cdi", "score": 65}
    out = attach_confidence_to_feature(f, _choices(good=True, n=5), {"max_turns": 5})
    assert out["confidence"]["level"] in {"directional", "exploratory"}


def test_attach_confidence_to_report():
    rep = {"features": [{"key": "cdi", "score": 70, "name": "CDI", "description": ""}]}
    out = attach_confidence_to_report(rep, _choices(), {"max_turns": 5})
    assert "confidence" in out["features"][0]
