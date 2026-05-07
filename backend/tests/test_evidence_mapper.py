from app.evidence_mapper import attach_evidence_to_report, bucket, build_evidence_cards, friendly_label


def _report():
    return {
        "session_id": "s1",
        "features": [
            {"name": "Decision Conflict Index", "key": "cdi", "score": 71.2, "evidence_count": 5},
            {"name": "Adaptive Decision-Making Quotient", "key": "adq", "score": 48.2, "evidence_count": 5},
        ],
    }


def _choices():
    return [
        {
            "id": "c1",
            "option_id": "A",
            "traits": {"risk": 0.7, "social": 0.4},
            "scene_metadata": {"time_pressure": 0.7},
            "telemetry": {"latency_ratio": 0.7, "timed_out": False, "hover_switch_count": 3, "changed_intent": True},
        },
        {
            "id": "c2",
            "option_id": "B",
            "traits": {"risk": 0.5, "social": 0.8},
            "scene_metadata": {"time_pressure": 0.4},
            "telemetry": {"latency_ratio": 0.4, "timed_out": False, "hover_switch_count": 1, "changed_intent": False},
        },
    ]


def test_bucket_mapping():
    assert bucket(10) == "low"
    assert bucket(40) == "balanced"
    assert bucket(90) == "high"


def test_labels_exist():
    assert friendly_label("cdi", "high")
    assert friendly_label("adq", "low")


def test_cdi_adq_evidence_has_expected_signals():
    cards = build_evidence_cards(_report(), _choices())
    cdi = next(c for c in cards if c["feature_key"] == "cdi")
    adq = next(c for c in cards if c["feature_key"] == "adq")
    assert any("hover switch" in e.lower() or "changed intent" in e.lower() for e in cdi["evidence"])
    assert any("timeout" in e.lower() or "pressure" in e.lower() for e in adq["evidence"])


def test_empty_choices_not_hallucinated():
    cards = build_evidence_cards(_report(), [])
    assert all("Insufficient evidence" in c["evidence"][0] for c in cards)


def test_attach_evidence_adds_cards_and_labels():
    report = attach_evidence_to_report(_report(), _choices())
    assert "evidence_cards" in report
    assert "label" in report["features"][0]
