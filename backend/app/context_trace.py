import hashlib
import json
import uuid
from datetime import datetime, timezone


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def build_context_trace(
    session,
    turn,
    pack,
    policy,
    query,
    retrieved,
    context_bundle,
    policy_trace_id=None,
    latency_ms=None,
) -> dict:
    retrieved_ids = [r.get("fragment", {}).get("id") for r in retrieved if r.get("fragment", {}).get("id")]
    retrieval_scores = {r.get("fragment", {}).get("id", f"frag_{i}"): r.get("score", 0.0) for i, r in enumerate(retrieved)}
    return {
        "id": str(uuid.uuid4()),
        "session_id": session.get("id"),
        "scene_id": None,
        "turn": int(turn),
        "scenario_pack_id": (pack or {}).get("id"),
        "policy_trace_id": policy_trace_id,
        "context_version": "context_v1",
        "query_json": query,
        "retrieved_fragment_ids": retrieved_ids,
        "retrieval_scores_json": retrieval_scores,
        "context_bundle_json": context_bundle,
        "context_hash": sha256_json(context_bundle),
        "prompt_hash": None,
        "output_hash": None,
        "latency_ms": latency_ms,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
