from app.benchmarks import percentile, safe_rate, summarize_latencies


def test_percentile_basic():
    vals = [1, 2, 3, 4, 5]
    assert percentile(vals, 0.5) == 3
    assert percentile(vals, 0.95) >= 4.5


def test_percentile_empty():
    assert percentile([], 0.5) is None


def test_summarize_latencies():
    summary = summarize_latencies([10, 20, 30, 40, 50])
    assert summary["samples"] == 5
    assert summary["p50_ms"] == 30
    assert summary["p95_ms"] is not None
    assert summary["p99_ms"] is not None


def test_safe_rate_zero():
    assert safe_rate(1, 0) == 0.0
