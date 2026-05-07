from time import perf_counter
import uuid

from .trace_utils import (
    make_request_id,
    new_span_id,
    parse_traceparent,
    safe_trace_json,
    sha256_json,
    sha256_text,
)


def extract_provider_metadata(response) -> dict:
    out = {"response_model": None, "token_usage_input": None, "token_usage_output": None, "provider_request_id": None}
    try:
        out["response_model"] = getattr(response, "model", None)
        usage = getattr(response, "usage", None)
        if usage:
            out["token_usage_input"] = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
            out["token_usage_output"] = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
        out["provider_request_id"] = getattr(response, "id", None)
    except Exception:
        pass
    return out


def build_generation_trace_start(
    session: dict,
    turn: int,
    provider: str,
    model: str | None,
    prompt: str | None = None,
    policy: dict | None = None,
    context_bundle: dict | None = None,
    policy_trace: dict | None = None,
    context_trace: dict | None = None,
    traceparent: str | None = None,
    operation_name: str = "generate_scene",
) -> dict:
    parsed = parse_traceparent(traceparent)
    prompt_hash = sha256_text(prompt or "") if prompt else None
    return {
        "id": str(uuid.uuid4()),
        "session_id": session.get("id"),
        "scene_id": None,
        "turn": int(turn),
        "trace_id": parsed["trace_id"],
        "span_id": new_span_id(),
        "parent_trace_id": parsed.get("parent_trace_id"),
        "request_id": make_request_id(),
        "trace_kind": "generation",
        "provider": provider,
        "request_model": model,
        "response_model": None,
        "operation_name": operation_name,
        "status": "started",
        "error_type": None,
        "duration_ms": None,
        "prompt_hash": prompt_hash,
        "context_hash": sha256_json(context_bundle or {}) if context_bundle else None,
        "policy_hash": sha256_json(policy or {}) if policy else None,
        "response_hash": None,
        "token_usage_input": None,
        "token_usage_output": None,
        "fallback_reason": None,
        "policy_version": (policy or {}).get("policy_version"),
        "context_version": (context_bundle or {}).get("context_version"),
        "prompt_template_version": (policy or {}).get("prompt_version"),
        "trace_json": safe_trace_json(
            {
                "policy_summary": {
                    "target_construct": (policy or {}).get("target_construct"),
                    "difficulty": (policy or {}).get("difficulty"),
                },
                "context_summary": {
                    "fragment_count": len((context_bundle or {}).get("retrieved_fragments", [])),
                    "avoid_repetition_count": len((context_bundle or {}).get("avoid_repetition", [])),
                },
                "policy_trace_id": (policy_trace or {}).get("id"),
                "context_trace_id": (context_trace or {}).get("id"),
                "prompt_hash": prompt_hash,
                "prompt_preview": (prompt or "")[:300],
            }
        ),
    }


def finalize_generation_trace(
    trace: dict,
    scene: dict | None,
    status: str,
    started_at_monotonic: float,
    provider_response_metadata: dict | None = None,
    fallback_reason: str | None = None,
    error_type: str | None = None,
    validation: dict | None = None,
) -> dict:
    provider_response_metadata = provider_response_metadata or {}
    trace = dict(trace)
    trace["status"] = status
    trace["duration_ms"] = int((perf_counter() - started_at_monotonic) * 1000)
    trace["scene_id"] = scene.get("id") if scene else None
    trace["response_hash"] = sha256_json(scene) if scene else None
    trace["response_model"] = provider_response_metadata.get("response_model")
    trace["token_usage_input"] = provider_response_metadata.get("token_usage_input")
    trace["token_usage_output"] = provider_response_metadata.get("token_usage_output")
    trace["fallback_reason"] = fallback_reason
    trace["error_type"] = error_type
    trace["trace_json"] = safe_trace_json(
        {
            **(trace.get("trace_json") or {}),
            "validation": validation or {},
            "provider_request_id": provider_response_metadata.get("provider_request_id"),
        }
    )
    return trace
