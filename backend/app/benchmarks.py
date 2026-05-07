from __future__ import annotations


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(float(v) for v in values)
    if len(s) == 1:
        return s[0]
    idx = (len(s) - 1) * max(0.0, min(1.0, q))
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def summarize_latencies(values_ms: list[float]) -> dict:
    if not values_ms:
        return {"samples": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None, "min_ms": None, "max_ms": None}
    vals = [float(v) for v in values_ms]
    return {
        "samples": len(vals),
        "p50_ms": percentile(vals, 0.50),
        "p95_ms": percentile(vals, 0.95),
        "p99_ms": percentile(vals, 0.99),
        "min_ms": min(vals),
        "max_ms": max(vals),
    }


def format_benchmark_result(**kwargs) -> dict:
    return dict(kwargs)


def safe_rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return float(count) / float(total)
