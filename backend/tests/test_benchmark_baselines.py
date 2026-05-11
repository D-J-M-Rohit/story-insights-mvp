from app.benchmark_baselines import attach_benchmark_comparisons, comparison_band


def test_comparison_band_classification():
    assert comparison_band(20) == "below reference band"
    assert comparison_band(50) == "within reference band"
    assert comparison_band(80) == "above reference band"


def test_attach_benchmark_comparisons_adds_known_features_only():
    report = {
        "features": [
            {"key": "cdi", "name": "Conflict Deliberation", "score": 61},
            {"key": "unknown_feature", "name": "Unknown", "score": 70},
        ]
    }
    out = attach_benchmark_comparisons(report)
    comparisons = out.get("benchmark_comparisons", [])
    assert len(comparisons) == 1
    assert comparisons[0]["feature_key"] == "cdi"
    assert comparisons[0]["band"] == "within reference band"
