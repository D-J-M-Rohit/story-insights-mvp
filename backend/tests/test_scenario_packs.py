from app.prompt_policy import CORE_CONSTRUCTS
from app.scenario_packs import load_builtin_packs, validate_pack


def test_builtin_packs_load():
    packs = load_builtin_packs()
    assert len(packs) >= 3


def test_each_pack_validates():
    for pack in load_builtin_packs():
        valid, errors = validate_pack(pack)
        assert valid, errors


def test_each_pack_has_construct_targets_and_safety():
    for pack in load_builtin_packs():
        target_min = pack["blueprint"]["target_min"]
        for construct in CORE_CONSTRUCTS:
            assert construct in target_min
        curve = pack["difficulty_curve"]
        assert all(0 <= float(v) <= 1 for v in curve)
        assert pack["safety_profile"]["forbid"]
