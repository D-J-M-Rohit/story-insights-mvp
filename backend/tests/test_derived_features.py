from app.evidence_mapper import build_derived_features


def _session():
    return {"id": "s1", "max_turns": 5}


def _report():
    return {
        "session_id": "s1",
        "features": [
            {"name": "Decision Conflict Index", "key": "cdi", "score": 70.2, "description": "x"},
            {"name": "Adaptive Decision-Making Quotient", "key": "adq", "score": 48.1, "description": "x"},
        ],
    }


def _choices():
    return [
        {
            "id": "c1",
            "traits": {"risk": 0.6, "social": 0.6, "empathy": 0.4, "decisiveness": 0.7, "emotional_regulation": 0.5},
            "telemetry": {"latency_ms": 12000, "latency_ratio": 0.5, "timed_out": False, "hover_switch_count": 2, "changed_intent": True},
            "scene_metadata": {"time_pressure": 0.7},
            "time_limit_sec": 45,
        }
    ]


def test_build_derived_features_per_feature():
    rows = build_derived_features(_session(), _report(), _choices())
    assert len(rows) == len(_report()["features"])


def test_rows_include_confidence_fields():
    row = build_derived_features(_session(), _report(), _choices())[0]
    assert "confidence_low" in row and "confidence_high" in row and "confidence_margin" in row
    assert "evidence_count" in row


def test_no_clinical_hiring_language_in_labels_or_notes():
    rows = build_derived_features(_session(), _report(), _choices())
    text = " ".join([str(r.get("feature_label", "")) + " " + str(r.get("evidence_json", {})) for r in rows]).lower()
    assert "fit for job" not in text
    assert "employment-fit" not in text
