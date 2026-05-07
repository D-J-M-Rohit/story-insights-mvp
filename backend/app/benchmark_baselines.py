MVP_BASELINES = {
    "cdi": {"label": "Conflict / deliberation", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more deliberative or conflicted"},
    "adq": {"label": "Adaptability under pressure", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more adaptive under pressure"},
    "risk_tolerance": {"label": "Risk style", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more risk-tolerant"},
    "social_influence_sensitivity": {"label": "Social orientation", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more socially influenced or collaborative"},
    "time_pressure_resilience": {"label": "Deadline resilience", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more resilient under deadlines"},
    "consistency": {"label": "Decision stability", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more stable across decisions"},
    "engagement": {"label": "Interaction signal", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more actively engaged"},
    "extraversion_proxy": {"label": "Extraversion proxy", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more socially assertive in choices"},
    "neuroticism_proxy": {"label": "Neuroticism proxy", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more tension-sensitive in this session"},
    "psychoticism_proxy": {"label": "Psychoticism proxy", "baseline_mid": 50, "low_threshold": 35, "high_threshold": 65, "higher_is": "more bold or lower-empathy in selected choices"},
}

DISCLAIMER = "Compared against an internal MVP reference band only. This is not a clinical, population, or hiring norm."


def comparison_band(score: float, low_threshold: float = 35, high_threshold: float = 65) -> str:
    if score < low_threshold:
        return "below MVP reference band"
    if score >= high_threshold:
        return "above MVP reference band"
    return "within MVP reference band"


def attach_benchmark_comparisons(report: dict) -> dict:
    features = report.get("features") or []
    out = []
    for feature in features:
        key = feature.get("key")
        if key not in MVP_BASELINES:
            continue
        baseline = MVP_BASELINES[key]
        score = float(feature.get("score", 0))
        out.append(
            {
                "feature_key": key,
                "metric_name": feature.get("name", key),
                "label": baseline["label"],
                "score": score,
                "baseline_mid": baseline["baseline_mid"],
                "low_threshold": baseline["low_threshold"],
                "high_threshold": baseline["high_threshold"],
                "band": comparison_band(score, baseline["low_threshold"], baseline["high_threshold"]),
                "higher_is": baseline["higher_is"],
                "note": DISCLAIMER,
            }
        )
    report["benchmark_comparisons"] = out
    return report
