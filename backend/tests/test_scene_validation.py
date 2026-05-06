from app.scene_validation import validate_scene_against_policy


def _policy():
    return {
        "target_construct": "empathy",
        "difficulty": 0.58,
        "ambiguity": 0.52,
        "time_pressure": 0.61,
        "conflict_affordance": 0.57,
        "time_limit_sec": 45,
    }


def _valid_scene():
    return {
        "title": "Team dilemma",
        "scene": "A teammate asks for help near a deadline.",
        "time_limit_sec": 45,
        "scene_metadata": {
            "target_construct": "empathy",
            "difficulty": 0.6,
            "ambiguity": 0.55,
            "time_pressure": 0.65,
            "conflict_affordance": 0.58,
        },
        "options": [
            {"id": "A", "text": "Offer immediate support and re-plan work.", "traits": {"risk": 0.3, "social": 0.7, "empathy": 0.9, "decisiveness": 0.5, "emotional_regulation": 0.6}, "construct_tags": ["empathy"]},
            {"id": "B", "text": "Decline and focus only on your tasks.", "traits": {"risk": 0.3, "social": 0.4, "empathy": 0.4, "decisiveness": 0.6, "emotional_regulation": 0.5}, "construct_tags": ["empathy"]},
            {"id": "C", "text": "Set a smaller help window with clear boundaries.", "traits": {"risk": 0.3, "social": 0.6, "empathy": 0.65, "decisiveness": 0.7, "emotional_regulation": 0.7}, "construct_tags": ["empathy"]},
        ],
    }


def test_valid_scene_passes():
    out = validate_scene_against_policy(_valid_scene(), _policy(), {})
    assert out["valid"] is True


def test_missing_option_fails():
    scene = _valid_scene()
    scene["options"] = scene["options"][:2]
    out = validate_scene_against_policy(scene, _policy(), {})
    assert out["valid"] is False


def test_wrong_target_construct_fails():
    scene = _valid_scene()
    scene["scene_metadata"]["target_construct"] = "risk"
    out = validate_scene_against_policy(scene, _policy(), {})
    assert out["valid"] is False


def test_trait_out_of_range_fails():
    scene = _valid_scene()
    scene["options"][0]["traits"]["empathy"] = 1.2
    out = validate_scene_against_policy(scene, _policy(), {})
    assert out["valid"] is False


def test_target_spread_too_low_fails():
    scene = _valid_scene()
    for opt in scene["options"]:
        opt["traits"]["empathy"] = 0.6
    out = validate_scene_against_policy(scene, _policy(), {})
    assert out["valid"] is False


def test_forbidden_terms_fail():
    scene = _valid_scene()
    scene["scene"] = "Provide clinical diagnosis and hiring decision."
    out = validate_scene_against_policy(scene, _policy(), {})
    assert out["valid"] is False
