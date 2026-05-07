from .telemetry import telemetry_summary_for_evidence


DISCLAIMER = "Experimental reflection only; not a clinical, diagnostic, or hiring assessment."


def bucket(score: float) -> str:
    if score < 35:
        return "low"
    if score < 65:
        return "balanced"
    return "high"


LABELS = {
    "adq": {"low": "needs more support under pressure", "balanced": "steady under pressure", "high": "adaptive under pressure"},
    "cdi": {"low": "direct decision style", "balanced": "reflective decision style", "high": "deliberative but potentially conflicted"},
    "risk_tolerance": {"low": "cautious action style", "balanced": "measured risk style", "high": "bold action style"},
    "social_influence_sensitivity": {"low": "independent decision style", "balanced": "balanced social awareness", "high": "collaborative decision style"},
    "time_pressure_resilience": {"low": "slower under deadlines", "balanced": "moderate deadline resilience", "high": "strong deadline resilience"},
    "consistency": {"low": "context-sensitive decision pattern", "balanced": "moderately stable decision pattern", "high": "stable decision pattern"},
    "engagement": {"low": "limited interaction signal", "balanced": "steady participation", "high": "active exploration"},
    "psychoticism_proxy": {"low": "lower risk / higher empathy signal", "balanced": "mixed risk-empathy signal", "high": "higher risk / lower empathy signal"},
    "extraversion_proxy": {"low": "reserved decision signal", "balanced": "balanced social assertiveness signal", "high": "socially assertive decision signal"},
    "neuroticism_proxy": {"low": "lower stress-reactivity signal", "balanced": "moderate stress-reactivity signal", "high": "higher stress-reactivity signal"},
}


def friendly_label(feature_key: str, b: str) -> str:
    return LABELS.get(feature_key, {}).get(b, "descriptive signal")


def _top_choice_ids(choices, key, n=3):
    scored = []
    for ch in choices:
        traits = ch.get("traits") or {}
        scored.append((ch.get("id"), float(traits.get(key, 0.0) or 0.0)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [sid for sid, _ in scored[:n] if sid]


def build_evidence_cards(report: dict, choices: list[dict]) -> list[dict]:
    summary = telemetry_summary_for_evidence(choices)
    cards = []
    for f in report.get("features", []):
        key = f.get("key")
        score = float(f.get("score", 0.0))
        b = bucket(score)
        evidence = []
        components = {}
        source_choice_ids = [c.get("id") for c in choices if c.get("id")]
        completed = max(summary["completed"], 1)
        if key == "cdi":
            evidence.append(f"{summary['choices_after_65pct']} of {summary['completed']} choices were submitted after more than 65% of available time.")
            evidence.append(f"Average hover switch count was {summary['avg_hover_switch_count']}.")
            evidence.append(f"Changed intent occurred in {summary['changed_intent_count']} scenes.")
            components = {
                "changed_intent_rate": round(summary["changed_intent_count"] / completed, 4),
                "prolonged_hesitation_rate": round(summary["prolonged_hesitation_count"] / completed, 4),
                "avg_hover_switch_count": summary["avg_hover_switch_count"],
            }
        elif key == "adq":
            pressure = [c for c in choices if float((c.get("scene_metadata") or {}).get("time_pressure", 0.0)) >= 0.5]
            timeout = summary["timeout_count"]
            evidence.append(f"Timeout count was {timeout} across {summary['completed']} completed choices.")
            evidence.append(f"{len(pressure)} scenes were under elevated time pressure.")
            evidence.append("No timeout evidence supports stronger adaptability under pressure." if timeout == 0 else "Timeouts suggest reduced adaptability in pressured scenes.")
            components = {"timeout_count": timeout, "pressure_scene_count": len(pressure)}
        elif key == "risk_tolerance":
            avg = sum(float((c.get('traits') or {}).get('risk', 0.0)) for c in choices) / completed
            high = sum(1 for c in choices if float((c.get("traits") or {}).get("risk", 0.0)) >= 0.65)
            evidence.extend([f"Average selected risk trait was {round(avg,3)}.", f"{high} choices had high risk trait (>=0.65)."])
            components = {"avg_selected_risk": round(avg, 4), "high_risk_choice_count": high}
            source_choice_ids = _top_choice_ids(choices, "risk")
        elif key == "social_influence_sensitivity":
            avg = sum(float((c.get('traits') or {}).get('social', 0.0)) for c in choices) / completed
            high = sum(1 for c in choices if float((c.get("traits") or {}).get("social", 0.0)) >= 0.65)
            evidence.extend([f"Average selected social trait was {round(avg,3)}.", f"{high} choices had high social trait (>=0.65)."])
            components = {"avg_selected_social": round(avg, 4), "high_social_choice_count": high}
            source_choice_ids = _top_choice_ids(choices, "social")
        elif key == "time_pressure_resilience":
            evidence.extend(
                [
                    f"Average latency ratio was {summary['avg_latency_ratio']}.",
                    f"Timeout count was {summary['timeout_count']}.",
                    f"Average focus loss count was {summary['avg_focus_lost_count']}.",
                ]
            )
            components = {
                "avg_latency_ratio": summary["avg_latency_ratio"],
                "timeout_count": summary["timeout_count"],
                "avg_focus_lost_count": summary["avg_focus_lost_count"],
            }
        elif key == "consistency":
            evidence.append("Score reflects stability of decision profile across varied contexts.")
            evidence.append("Lower values may indicate context-sensitive adaptation rather than pure inconsistency.")
            components = {"interpretation_status": f.get("interpretation_status")}
        elif key == "engagement":
            evidence.extend(
                [
                    f"Completed choices: {summary['completed']}.",
                    f"Average hover switch count: {summary['avg_hover_switch_count']}.",
                    f"Timeout count: {summary['timeout_count']}.",
                ]
            )
            components = {
                "completed": summary["completed"],
                "avg_hover_switch_count": summary["avg_hover_switch_count"],
                "timeout_count": summary["timeout_count"],
            }
        else:
            evidence.append("Feature is derived from deterministic scoring formulas and normalized choice signals.")
            components = {"evidence_count": f.get("evidence_count", 0)}
        if not choices:
            evidence = ["Insufficient evidence: no completed choices were available."]
            source_choice_ids = []
        cards.append(
            {
                "feature_key": key,
                "feature_name": f.get("name", key),
                "score": score,
                "bucket": b,
                "label": friendly_label(key, b),
                "evidence": evidence[:3],
                "components": components,
                "source_choice_ids": source_choice_ids,
                "disclaimer": DISCLAIMER,
            }
        )
    return cards


def build_derived_features(session: dict, report: dict, choices: list[dict]) -> list[dict]:
    out = []
    for card in build_evidence_cards(report, choices):
        out.append(
            {
                "session_id": session.get("id"),
                "report_id": report.get("session_id"),
                "feature_key": card["feature_key"],
                "feature_name": card["feature_name"],
                "feature_score": card["score"],
                "feature_bucket": card["bucket"],
                "feature_label": card["label"],
                "evidence_json": {"evidence": card["evidence"], "components": card["components"], "disclaimer": card["disclaimer"]},
                "source_choice_ids": card.get("source_choice_ids", []),
                "scorer_version": "scoring_v1",
            }
        )
    return out


def attach_evidence_to_report(report: dict, choices: list[dict]) -> dict:
    report = dict(report)
    cards = build_evidence_cards(report, choices)
    report["evidence_cards"] = cards
    labels = {c["feature_key"]: c for c in cards}
    for f in report.get("features", []):
        card = labels.get(f.get("key"))
        if card:
            f["bucket"] = card["bucket"]
            f["label"] = card["label"]
    return report
