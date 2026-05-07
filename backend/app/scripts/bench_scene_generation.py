import json
import os
import time

import httpx

from app.benchmarks import safe_rate, summarize_latencies


def main():
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    token = os.getenv("TOKEN", "")
    n = int(os.getenv("N", "50"))
    scenario = os.getenv("SCENARIO", "workplace")
    max_turns = int(os.getenv("MAX_TURNS", "5"))
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    latencies = []
    errors = 0
    fallbacks = 0
    with httpx.Client(timeout=30.0) as client:
        for _ in range(n):
            s = client.post(
                f"{base_url}/api/v1/sessions",
                json={"scenario": scenario, "max_turns": max_turns},
                headers=headers,
            )
            if s.status_code != 200:
                errors += 1
                continue
            session_id = s.json()["id"]
            t0 = time.perf_counter()
            r = client.post(f"{base_url}/api/v1/scenes/next", json={"session_id": session_id}, headers=headers)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            if r.status_code != 200:
                errors += 1
                continue
            if (r.json().get("debug") or {}).get("fallback_used"):
                fallbacks += 1
    summary = summarize_latencies(latencies)
    out = {
        **summary,
        "median_ms": summary.get("p50_ms"),
        "error_rate": safe_rate(errors, n),
        "fallback_rate": safe_rate(fallbacks, n),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
