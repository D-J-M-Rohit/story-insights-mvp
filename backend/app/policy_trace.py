import hashlib
import json
import uuid
from datetime import datetime, timezone


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def build_output_hash(scene: dict) -> str:
    return sha256_json(scene or {})


def build_policy_trace(
    session_id: str,
    turn: int,
    scenario_pack_id: str,
    prompt_version: str,
    policy_version: str,
    provider: str,
    model_snapshot: str,
    policy_input: dict,
    policy_output: dict,
    prompt_text: str,
    prompt_template_id: str | None = None,
):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "scene_id": None,
        "turn": turn,
        "scenario_pack_id": scenario_pack_id,
        "prompt_template_id": prompt_template_id,
        "prompt_version": prompt_version,
        "policy_version": policy_version,
        "provider": provider,
        "model_snapshot": model_snapshot,
        "policy_input_json": policy_input,
        "policy_output_json": policy_output,
        "prompt_hash": hashlib.sha256((prompt_text or "").encode("utf-8")).hexdigest(),
        "output_hash": None,
        "validation_json": {},
        "fallback_reason": None,
        "latency_ms": None,
        "created_at": now,
    }
