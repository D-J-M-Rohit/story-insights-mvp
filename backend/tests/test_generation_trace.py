from time import perf_counter

from app.generation_trace import build_generation_trace_start, finalize_generation_trace


def _session():
    return {"id": "s1"}


def test_build_start_trace_has_ids_and_hashes():
    trace = build_generation_trace_start(
        session=_session(),
        turn=1,
        provider="mock",
        model="mock",
        prompt="hello",
        policy={"policy_version": "policy_v1"},
        context_bundle={"context_version": "context_v1"},
    )
    assert len(trace["trace_id"]) == 32
    assert len(trace["span_id"]) == 16
    assert trace["prompt_hash"].startswith("sha256:")
    assert trace["context_hash"].startswith("sha256:")


def test_finalize_sets_response_and_duration():
    start = build_generation_trace_start(_session(), 1, "mock", "mock", prompt="x")
    out = finalize_generation_trace(
        start,
        scene={"id": "sc1", "scene": "text"},
        status="ok",
        started_at_monotonic=perf_counter(),
        provider_response_metadata={"response_model": "mock"},
        validation={"valid": True},
    )
    assert out["response_hash"].startswith("sha256:")
    assert out["duration_ms"] is not None


def test_sensitive_redacted_in_trace_json():
    start = build_generation_trace_start(
        _session(),
        1,
        "mock",
        "mock",
        prompt="x",
        policy={"token": "abc", "password": "p"},
    )
    raw = str(start["trace_json"]).lower()
    assert "abc" not in raw and "password" not in raw


def test_fallback_status_records_reason():
    start = build_generation_trace_start(_session(), 1, "openai", "gpt")
    out = finalize_generation_trace(start, scene={"id": "s"}, status="fallback", started_at_monotonic=perf_counter(), fallback_reason="provider_exception")
    assert out["status"] == "fallback"
    assert out["fallback_reason"] == "provider_exception"
