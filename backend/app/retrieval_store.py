from __future__ import annotations


def normalize_tags(tags) -> set[str]:
    if not tags:
        return set()
    return {str(t).strip().lower().replace(" ", "_") for t in tags if str(t).strip()}


def clamp(v, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return lo


def difficulty_match_score(fragment: dict, difficulty: float) -> float:
    d = clamp(difficulty)
    lo = float(fragment.get("difficulty_min", 0.0))
    hi = float(fragment.get("difficulty_max", 1.0))
    if lo <= d <= hi:
        return 1.0
    if d < lo:
        return clamp(1.0 - (lo - d) / 0.5)
    return clamp(1.0 - (d - hi) / 0.5)


def tag_overlap_score(fragment_tags: set[str], query_tags: set[str]) -> float:
    if not query_tags:
        return 0.0
    union = fragment_tags | query_tags
    if not union:
        return 0.0
    return len(fragment_tags & query_tags) / len(union)


def content_type_priority(content_type: str) -> float:
    table = {
        "construct_anchor": 1.0,
        "narrative_anchor": 0.9,
        "consequence_pattern": 0.7,
        "style_anchor": 0.5,
        "safety_rule": 0.4,
        "anti_pattern": 0.3,
    }
    return table.get((content_type or "").lower(), 0.3)


def score_fragment(fragment, target_construct, query_tags, difficulty, used_fragment_ids=None) -> dict:
    used_fragment_ids = used_fragment_ids or set()
    f_tags = normalize_tags(fragment.get("tags", []))
    construct_match = 1.0 if target_construct in f_tags else 0.0
    overlap = tag_overlap_score(f_tags, normalize_tags(query_tags))
    diff_match = difficulty_match_score(fragment, difficulty)
    unused_bonus = 1.0 if fragment.get("id") not in used_fragment_ids else 0.0
    ctype = content_type_priority(fragment.get("content_type", "narrative_anchor"))
    score = 0.35 * construct_match + 0.25 * overlap + 0.20 * diff_match + 0.10 * unused_bonus + 0.10 * ctype
    return {
        "fragment": fragment,
        "score": round(score, 4),
        "reasons": {
            "construct_match": construct_match,
            "tag_overlap": round(overlap, 4),
            "difficulty_match": round(diff_match, 4),
            "unused_bonus": unused_bonus,
            "content_type_priority": ctype,
        },
    }


def _query_tags(policy, pack):
    tags = {policy.get("target_construct", "")}
    setting = ((pack.get("characteristic_features") or {}).get("setting") or "").lower()
    tags.update(setting.replace(",", " ").split())
    if float(policy.get("time_pressure", 0)) >= 0.65:
        tags.update({"deadline", "urgency", "pressure"})
    if float(policy.get("ambiguity", 0)) >= 0.60:
        tags.update({"ambiguity", "uncertainty"})
    if float(policy.get("conflict_affordance", 0)) >= 0.60:
        tags.update({"conflict", "tradeoff"})
    by_construct = {
        "risk": {"risk", "tradeoff", "consequence"},
        "social": {"team", "communication", "stakeholder"},
        "empathy": {"support", "impact", "perspective"},
        "decisiveness": {"deadline", "action", "priority"},
        "emotional_regulation": {"pressure", "tone", "calm"},
    }
    tags.update(by_construct.get(policy.get("target_construct"), set()))
    return normalize_tags(tags)


def retrieve_fragments(pack, policy, history_summary="", used_fragment_ids=None, final_k=5) -> list[dict]:
    used_fragment_ids = used_fragment_ids or set()
    fragments = pack.get("fragments") or []
    target = policy.get("target_construct", "social")
    query_tags = _query_tags(policy, pack)
    scored = [score_fragment(f, target, query_tags, policy.get("difficulty", 0.5), used_fragment_ids) for f in fragments]
    scored.sort(key=lambda x: x["score"], reverse=True)

    selected = []
    construct_anchor = next((s for s in scored if s["fragment"].get("content_type") == "construct_anchor" and target in normalize_tags(s["fragment"].get("tags", []))), None)
    if construct_anchor:
        selected.append(construct_anchor)
    narrative = next((s for s in scored if s["fragment"].get("content_type") == "narrative_anchor"), None)
    if narrative and narrative not in selected:
        selected.append(narrative)
    consequence = next((s for s in scored if s["fragment"].get("content_type") == "consequence_pattern"), None)
    if consequence and consequence not in selected:
        selected.append(consequence)
    style_or_safety = next((s for s in scored if s["fragment"].get("content_type") in {"style_anchor", "safety_rule"}), None)
    if style_or_safety and style_or_safety not in selected:
        selected.append(style_or_safety)

    for s in scored:
        if s in selected:
            continue
        if s["fragment"].get("content_type") == "anti_pattern":
            continue
        selected.append(s)
        if len(selected) >= final_k:
            break
    return selected[:final_k]


def collect_anti_patterns(pack, scenes, policy, limit=4) -> list[str]:
    items = []
    anti = [f for f in (pack.get("fragments") or []) if f.get("content_type") == "anti_pattern"]
    for frag in anti[:limit]:
        items.append(str(frag.get("text", "")).strip())
    if scenes:
        prev = scenes[-1]
        if prev.get("title"):
            items.append(f"Avoid repeating the previous scene title: {prev['title']}")
        if len(scenes) > 1:
            prior = scenes[-2]
            if prior.get("title"):
                items.append(f"Avoid using the same central dilemma as turn {prior.get('turn')}: {prior['title']}")
        opts = (prev.get("options") or [])
        consensus_like = sum(1 for o in opts if "team" in str(o.get("text", "")).lower() or "consensus" in str(o.get("text", "")).lower())
        if consensus_like >= 2:
            items.append("Avoid making the strongest option always a group-consensus action.")
    return items[:limit]


# TODO: Add sentence-transformers embeddings for semantic retrieval.
# TODO: Add FAISS HNSW index for scalable vector search.
# TODO: Add cross-encoder reranking if retrieval quality becomes important.
# TODO: Add retrieval evaluation metrics for context relevance and coverage.
