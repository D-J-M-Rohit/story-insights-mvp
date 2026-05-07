from app.retrieval_store import (
    difficulty_match_score,
    normalize_tags,
    retrieve_fragments,
    score_fragment,
)


def _pack():
    return {
        "characteristic_features": {"setting": "modern workplace"},
        "fragments": [
            {
                "id": "a1",
                "content_type": "construct_anchor",
                "tags": ["empathy", "support"],
                "difficulty_min": 0.2,
                "difficulty_max": 0.8,
                "text": "Anchor",
            },
            {
                "id": "n1",
                "content_type": "narrative_anchor",
                "tags": ["team", "communication"],
                "difficulty_min": 0.2,
                "difficulty_max": 0.9,
                "text": "Narrative",
            },
            {
                "id": "anti1",
                "content_type": "anti_pattern",
                "tags": ["repetition"],
                "difficulty_min": 0.0,
                "difficulty_max": 1.0,
                "text": "Avoid repeats",
            },
        ],
    }


def test_normalize_tags():
    assert normalize_tags([" Team ", "deadline urgency"]) == {"team", "deadline_urgency"}


def test_difficulty_score_inside_range_is_one():
    frag = {"difficulty_min": 0.3, "difficulty_max": 0.7}
    assert difficulty_match_score(frag, 0.5) == 1.0


def test_difficulty_score_decays_outside_range():
    frag = {"difficulty_min": 0.3, "difficulty_max": 0.7}
    assert 0 <= difficulty_match_score(frag, 0.95) < 1.0


def test_construct_match_increases_score():
    frag_match = {"id": "x", "content_type": "construct_anchor", "tags": ["empathy"], "difficulty_min": 0.2, "difficulty_max": 0.9}
    frag_nomatch = {"id": "y", "content_type": "construct_anchor", "tags": ["risk"], "difficulty_min": 0.2, "difficulty_max": 0.9}
    s1 = score_fragment(frag_match, "empathy", {"empathy"}, 0.5, set())["score"]
    s2 = score_fragment(frag_nomatch, "empathy", {"empathy"}, 0.5, set())["score"]
    assert s1 > s2


def test_used_fragment_loses_unused_bonus():
    frag = {"id": "used", "content_type": "narrative_anchor", "tags": ["empathy"], "difficulty_min": 0.2, "difficulty_max": 0.9}
    fresh = score_fragment(frag, "empathy", {"empathy"}, 0.5, set())["score"]
    used = score_fragment(frag, "empathy", {"empathy"}, 0.5, {"used"})["score"]
    assert fresh > used


def test_retrieve_includes_construct_and_narrative_and_not_only_anti():
    policy = {"target_construct": "empathy", "difficulty": 0.5, "time_pressure": 0.7, "ambiguity": 0.5, "conflict_affordance": 0.6}
    out = retrieve_fragments(_pack(), policy, used_fragment_ids=set(), final_k=5)
    types = {row["fragment"]["content_type"] for row in out}
    assert "construct_anchor" in types
    assert "narrative_anchor" in types
    assert types != {"anti_pattern"}
