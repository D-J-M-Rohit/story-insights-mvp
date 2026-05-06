from app.prompt_policy import decide_policy, map_time_pressure_to_limit
from app.scenario_packs import get_default_pack_for_scenario


def _session(max_turns=5):
    return {"id": "sess-1", "scenario": "workplace", "max_turns": max_turns}


def _choice(target_construct="social", difficulty=0.5, latency_ms=45000, timed_out=False, switches=2, changed=False):
    return {
        "scene_metadata": {"target_construct": target_construct, "difficulty": difficulty},
        "telemetry": {
            "latency_ms": latency_ms,
            "timed_out": timed_out,
            "hover_switch_count": switches,
            "changed_intent": changed,
        },
        "time_limit_sec": 45,
        "traits": {"risk": 0.5, "social": 0.5, "empathy": 0.5, "decisiveness": 0.5, "emotional_regulation": 0.5},
    }


def test_policy_is_deterministic_for_same_inputs():
    pack = get_default_pack_for_scenario("workplace")
    p1 = decide_policy(_session(), [], pack, 1)
    p2 = decide_policy(_session(), [], pack, 1)
    assert p1 == p2


def test_no_choices_returns_valid_policy():
    pack = get_default_pack_for_scenario("workplace")
    p = decide_policy(_session(), [], pack, 1)
    assert p["target_construct"] in {"risk", "social", "empathy", "decisiveness", "emotional_regulation"}
    assert 0.30 <= p["difficulty"] <= 0.85


def test_five_turn_session_covers_all_constructs():
    pack = get_default_pack_for_scenario("workplace")
    choices = []
    seen = set()
    for turn in range(1, 6):
        policy = decide_policy(_session(), choices, pack, turn)
        seen.add(policy["target_construct"])
        choices.append(_choice(policy["target_construct"], policy["difficulty"]))
    assert len(seen) == 5


def test_final_turn_forces_unmet_construct():
    pack = get_default_pack_for_scenario("workplace")
    choices = [_choice("social"), _choice("social"), _choice("social"), _choice("social")]
    policy = decide_policy(_session(), choices, pack, 5)
    assert policy["target_construct"] != "social"


def test_difficulty_delta_capped():
    pack = get_default_pack_for_scenario("workplace")
    choices = [_choice("social", difficulty=0.35, latency_ms=5000, timed_out=False, switches=0)]
    p = decide_policy(_session(), choices, pack, 2)
    assert abs(p["difficulty"] - 0.35) <= 0.12 + 1e-6


def test_time_pressure_maps_to_allowed_limits():
    limits = [map_time_pressure_to_limit(v) for v in [0.2, 0.4, 0.55, 0.7, 0.85]]
    assert limits == [75, 60, 45, 35, 25]
