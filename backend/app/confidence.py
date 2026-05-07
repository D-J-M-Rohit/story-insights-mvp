import math


def clamp(v, lo=0.0, hi=100.0):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return lo


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _usable(choice):
    return not bool((choice.get("telemetry") or {}).get("timed_out"))


def count_metric_evidence(feature_key: str, choices: list[dict]) -> int:
    choices = choices or []
    if feature_key == "time_pressure_resilience":
        pressure = [c for c in choices if safe_float((c.get("scene_metadata") or {}).get("time_pressure"), 0) >= 0.5]
        base = pressure if pressure else choices
        return sum(1 for c in base if _usable(c))
    if feature_key == "cdi":
        return sum(
            1
            for c in choices
            if (c.get("telemetry") or {}).get("latency_ms") is not None
            or (c.get("telemetry") or {}).get("hover_switch_count") is not None
            or (c.get("telemetry") or {}).get("changed_intent") is not None
        )
    if feature_key == "adq":
        return sum(1 for c in choices if (c.get("telemetry") or {}).get("latency_ms") is not None and c.get("time_limit_sec") is not None)
    if feature_key == "risk_tolerance":
        return sum(1 for c in choices if (c.get("traits") or {}).get("risk") is not None)
    if feature_key == "social_influence_sensitivity":
        return sum(1 for c in choices if (c.get("traits") or {}).get("social") is not None)
    if feature_key == "consistency":
        return sum(1 for c in choices if len([k for k in ("risk", "social", "empathy", "decisiveness", "emotional_regulation") if (c.get("traits") or {}).get(k) is not None]) >= 2)
    if feature_key == "engagement":
        return len(choices)
    if feature_key == "psychoticism_proxy":
        return sum(1 for c in choices if (c.get("traits") or {}).get("risk") is not None and (c.get("traits") or {}).get("empathy") is not None)
    if feature_key == "extraversion_proxy":
        return sum(1 for c in choices if (c.get("traits") or {}).get("social") is not None and (c.get("traits") or {}).get("decisiveness") is not None)
    if feature_key == "neuroticism_proxy":
        return sum(1 for c in choices if (c.get("traits") or {}).get("emotional_regulation") is not None and (c.get("telemetry") or {}).get("latency_ms") is not None)
    return sum(1 for c in choices if _usable(c))


def telemetry_quality_penalty(choices: list[dict]) -> float:
    choices = choices or []
    if not choices:
        return 18.0
    n = len(choices)
    timeout_rate = sum(1 for c in choices if (c.get("telemetry") or {}).get("timed_out")) / n
    missing_latency_rate = sum(1 for c in choices if (c.get("telemetry") or {}).get("latency_ms") is None) / n
    missing_traits_rate = sum(1 for c in choices if not (c.get("traits") or {})) / n
    missing_telemetry_rate = sum(1 for c in choices if not (c.get("telemetry") or {})) / n
    penalty = 6.0 * timeout_rate + 8.0 * missing_latency_rate + 8.0 * missing_traits_rate + 5.0 * missing_telemetry_rate
    return clamp(penalty, 0, 18)


def confidence_level(evidence_count: int, completed_count: int, expected_count: int, telemetry_penalty: float) -> str:
    if evidence_count < 3 or completed_count < max(3, expected_count * 0.6):
        return "insufficient_evidence"
    if evidence_count < 5 or telemetry_penalty >= 8:
        return "exploratory"
    return "directional"


def confidence_band(score: float, evidence_count: int, completed_count: int, expected_count: int, telemetry_penalty: float) -> dict:
    base_margin = 24.0 / math.sqrt(max(evidence_count, 1))
    raw_margin = base_margin + telemetry_penalty
    margin = clamp(raw_margin, 6, 30)
    low = clamp(score - margin, 0, 100)
    high = clamp(score + margin, 0, 100)
    lvl = confidence_level(evidence_count, completed_count, expected_count, telemetry_penalty)
    return {
        "confidence_level": lvl,
        "confidence_low": round(low, 2),
        "confidence_high": round(high, 2),
        "confidence_margin": round(margin, 2),
        "confidence_method": "mvp_evidence_weighted_v1",
        "evidence_count": int(evidence_count),
        "confidence_note": "Short-session estimate; treat as directional, not diagnostic.",
    }


def attach_confidence_to_feature(feature: dict, choices: list[dict], session: dict) -> dict:
    out = dict(feature)
    evidence_count = count_metric_evidence(out.get("key", ""), choices)
    completed = len(choices or [])
    expected = int((session or {}).get("max_turns", completed or 1) or 1)
    penalty = telemetry_quality_penalty(choices)
    band = confidence_band(safe_float(out.get("score"), 0), evidence_count, completed, expected, penalty)
    out["confidence"] = {
        "level": band["confidence_level"],
        "low": band["confidence_low"],
        "high": band["confidence_high"],
        "margin": band["confidence_margin"],
        "method": band["confidence_method"],
        "evidence_count": band["evidence_count"],
        "note": band["confidence_note"],
    }
    return out


def attach_confidence_to_report(report: dict, choices: list[dict], session: dict) -> dict:
    report = dict(report)
    features = []
    for feature in report.get("features", []):
        features.append(attach_confidence_to_feature(feature, choices, session))
    report["features"] = features
    return report
