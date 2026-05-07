from app.context_builder import build_context_bundle, summarize_history


def _session():
    return {"id": "s1", "scenario": "workplace", "max_turns": 5}


def _policy():
    return {
        "turn": 2,
        "target_construct": "empathy",
        "difficulty": 0.58,
        "ambiguity": 0.52,
        "time_pressure": 0.61,
        "conflict_affordance": 0.57,
        "scenario_pack_id": "workplace_core_v1",
    }


def _pack():
    return {
        "id": "workplace_core_v1",
        "characteristic_features": {"setting": "modern workplace"},
        "fragments": [
            {
                "id": "anchor1",
                "content_type": "construct_anchor",
                "tags": ["empathy", "support", "team"],
                "difficulty_min": 0.2,
                "difficulty_max": 0.9,
                "text": "Use empathy in communication under pressure.",
            },
            {
                "id": "nav1",
                "content_type": "narrative_anchor",
                "tags": ["stakeholder", "deadline"],
                "difficulty_min": 0.3,
                "difficulty_max": 0.8,
                "text": "A stakeholder requests urgent clarification before a review.",
            },
        ],
    }


def test_empty_history_returns_valid_bundle():
    bundle, trace = build_context_bundle(_session(), [], [], _policy(), _pack())
    assert bundle["context_version"] == "context_v1"
    assert isinstance(bundle["retrieved_fragments"], list)
    assert trace["context_hash"]


def test_summary_excludes_raw_telemetry():
    scenes = [{"id": "sc1", "turn": 1, "title": "Title"}]
    choices = [{"scene_id": "sc1", "option_text": "Sample", "telemetry": {"latency_ms": 12000}}]
    s = summarize_history(scenes, choices)
    assert "latency_ms" not in s


def test_bundle_has_policy_alignment_and_retrieval():
    bundle, _ = build_context_bundle(_session(), [], [], _policy(), _pack())
    assert bundle["policy_alignment"]["target_construct"] == "empathy"
    assert len(bundle["retrieved_fragments"]) >= 1


def test_context_trace_excludes_identity_secrets():
    bundle, trace = build_context_bundle(_session(), [], [], _policy(), _pack())
    body = str(trace)
    assert "password" not in body.lower()
    assert "token" not in body.lower()
    assert "email" not in body.lower()
    assert bundle["context_version"] == "context_v1"


def test_missing_fragments_falls_back():
    pack = {"id": "fallback_pack", "fragments": []}
    bundle, trace = build_context_bundle(_session(), [], [], _policy(), pack)
    assert bundle["retrieved_fragments"] == []
    assert trace["context_hash"]
