import json
import os
import time

import httpx

from app.benchmarks import safe_rate, summarize_latencies


def main():
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    token = os.getenv("TOKEN", "")
    n = int(os.getenv("N", "30"))
    scenario = os.getenv("SCENARIO", "workplace")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    retrieval_times = []
    total_times = []
    errors = 0
    fallback = 0
    with httpx.Client(timeout=30.0) as client:
        for _ in range(n):
            s = client.post(f"{base_url}/api/v1/sessions", json={"scenario": scenario, "max_turns": 5}, headers=headers)
            if s.status_code != 200:
                errors += 1
                continue
            sid = s.json()["id"]
            t0 = time.perf_counter()
            r = client.post(f"{base_url}/api/v1/scenes/next", json={"session_id": sid}, headers=headers)
            total_times.append((time.perf_counter() - t0) * 1000.0)
            if r.status_code != 200:
                errors += 1
                continue
            debug = r.json().get("debug") or {}
            if debug.get("retrieval_ms") is not None:
                retrieval_times.append(float(debug["retrieval_ms"]))
            if debug.get("fallback_used"):
                fallback += 1
    rt = summarize_latencies(retrieval_times)
    tt = summarize_latencies(total_times)
    out = {
        "samples": n,
        "retrieval_p50_ms": rt.get("p50_ms"),
        "retrieval_p95_ms": rt.get("p95_ms"),
        "total_p50_ms": tt.get("p50_ms"),
        "total_p95_ms": tt.get("p95_ms"),
        "total_p99_ms": tt.get("p99_ms"),
        "error_rate": safe_rate(errors, n),
        "fallback_rate": safe_rate(fallback, n),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
