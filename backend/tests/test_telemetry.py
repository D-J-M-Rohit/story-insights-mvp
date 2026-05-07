from app.telemetry import (
    derive_dwell_from_hover_log,
    dominant_dwell_option,
    engagement_signal,
    normalize_telemetry,
    stress_signal,
)


def test_normalize_old_telemetry():
    out = normalize_telemetry({"latency_ms": 1000, "hover_log": [], "hover_switch_count": 1, "changed_intent": False, "timed_out": False}, 45)
    assert "latency_ratio" in out


def test_latency_ratio_computed():
    out = normalize_telemetry({"latency_ms": 22500}, 45)
    assert 0.49 <= out["latency_ratio"] <= 0.51


def test_dwell_derived_from_hover_log():
    dwell = derive_dwell_from_hover_log(
        [
            {"event": "enter", "option_id": "A", "t_ms": 0},
            {"event": "leave", "option_id": "A", "t_ms": 1000},
        ]
    )
    assert dwell["A"] == 1000


def test_huge_hover_log_capped():
    log = [{"event": "enter", "option_id": "A", "t_ms": i} for i in range(200)]
    out = normalize_telemetry({"hover_log": log}, 45)
    assert len(out["hover_log"]) <= 80


def test_focus_defaults_and_dominant():
    out = normalize_telemetry({"hover_dwell_ms_by_option": {"A": 100, "B": 30, "C": 10}}, 45)
    assert out["focus_lost_count"] == 0
    assert dominant_dwell_option(out) == "A"


def test_signals_in_range():
    choice = {"telemetry": {"latency_ratio": 0.7, "timed_out": False, "hover_switch_count": 2, "changed_intent": True}}
    assert 0 <= stress_signal(choice) <= 1
    assert 0 <= engagement_signal(choice) <= 1
