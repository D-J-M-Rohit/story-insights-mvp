from __future__ import annotations

from time import perf_counter

from .context_trace import build_context_trace, sha256_json
from .retrieval_store import collect_anti_patterns, retrieve_fragments


def summarize_history(scenes, choices, max_items=3) -> str:
    snippets = []
    for scene in scenes[-max_items:]:
        choice = next((c for c in choices if c.get("scene_id") == scene.get("id")), None)
        if not choice:
            continue
        text = str(choice.get("option_text", "")).strip()
        if len(text) > 90:
            text = text[:87] + "..."
        snippets.append(f"Turn {scene.get('turn')}, user chose: {text}")
    summary = "Recent path: " + " ".join(snippets) if snippets else "Recent path: no prior choices."
    return summary[:700]


def recent_choice_cards(scenes, choices, max_items=3) -> list[dict]:
    cards = []
    for scene in scenes[-max_items:]:
        choice = next((c for c in choices if c.get("scene_id") == scene.get("id")), None)
        if not choice:
            continue
        text = str(choice.get("option_text", "")).strip()
        if len(text) > 160:
            text = text[:157] + "..."
        cards.append(
            {
                "turn": scene.get("turn"),
                "scene_title": scene.get("title"),
                "target_construct": (scene.get("scene_metadata") or {}).get("target_construct"),
                "selected_option_text": text,
            }
        )
    return cards


def used_fragment_ids_from_scenes(scenes) -> set[str]:
    out = set()
    for scene in scenes:
        ids = ((scene.get("scene_metadata") or {}).get("context_fragment_ids") or [])
        for item in ids:
            out.add(str(item))
    return out


def build_retrieval_query(session, policy, pack, history_summary) -> dict:
    return {
        "scenario": session.get("scenario"),
        "scenario_pack_id": pack.get("id"),
        "target_construct": policy.get("target_construct"),
        "difficulty": policy.get("difficulty"),
        "query_tags": sorted(
            [
                policy.get("target_construct", ""),
                "urgency" if float(policy.get("time_pressure", 0)) >= 0.65 else "",
                "uncertainty" if float(policy.get("ambiguity", 0)) >= 0.60 else "",
                "tradeoff" if float(policy.get("conflict_affordance", 0)) >= 0.60 else "",
            ]
        ),
        "history_summary_hash": sha256_json(history_summary or ""),
        "turn": policy.get("turn"),
    }


def compact_fragments(retrieved) -> list[dict]:
    compact = []
    for item in retrieved:
        frag = item.get("fragment", {})
        text = str(frag.get("text", ""))
        if len(text) > 300:
            text = text[:297] + "..."
        compact.append(
            {
                "id": frag.get("id"),
                "content_type": frag.get("content_type"),
                "tags": frag.get("tags", []),
                "text": text,
                "score": item.get("score", 0.0),
            }
        )
    return compact


def build_context_bundle(
    session: dict,
    scenes: list[dict],
    choices: list[dict],
    policy: dict,
    pack: dict,
    policy_trace_id: str | None = None,
) -> tuple[dict, dict]:
    started = perf_counter()
    fallback_reason = None
    try:
        history_summary = summarize_history(scenes, choices)
        cards = recent_choice_cards(scenes, choices)
        used = used_fragment_ids_from_scenes(scenes)
        retrieved = retrieve_fragments(pack, policy, history_summary=history_summary, used_fragment_ids=used, final_k=5)
        anti = collect_anti_patterns(pack, scenes, policy, limit=4)
        query = build_retrieval_query(session, policy, pack, history_summary)
    except Exception:
        history_summary = "Recent path: no prior choices."
        cards = []
        retrieved = []
        anti = collect_anti_patterns(pack or {}, scenes or [], policy or {}, limit=4)
        query = {"fallback_reason": "missing_pack_or_fragments"}
        fallback_reason = "missing_pack_or_fragments"

    bundle = {
        "context_version": "context_v1",
        "scenario_pack_id": (pack or {}).get("id"),
        "turn": policy.get("turn"),
        "history_summary": history_summary,
        "recent_choices": cards,
        "retrieved_fragments": compact_fragments(retrieved),
        "avoid_repetition": anti,
        "policy_alignment": {
            "target_construct": policy.get("target_construct"),
            "difficulty": policy.get("difficulty"),
            "ambiguity": policy.get("ambiguity"),
            "time_pressure": policy.get("time_pressure"),
            "conflict_affordance": policy.get("conflict_affordance"),
        },
    }
    if fallback_reason:
        bundle["fallback_reason"] = fallback_reason
        query["fallback_reason"] = fallback_reason
    latency = int((perf_counter() - started) * 1000)
    trace = build_context_trace(
        session=session,
        turn=policy.get("turn"),
        pack=pack or {},
        policy=policy,
        query=query,
        retrieved=retrieved,
        context_bundle=bundle,
        policy_trace_id=policy_trace_id,
        latency_ms=latency,
    )
    return bundle, trace
