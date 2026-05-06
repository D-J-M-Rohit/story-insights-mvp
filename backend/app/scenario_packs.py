import json
from pathlib import Path

from .store import get_active_scenario_pack_for_scenario, upsert_scenario_pack

CORE_CONSTRUCTS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]
PACKS_DIR = Path(__file__).parent / "scenario_packs_data"


def load_pack_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_pack(pack: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ("id", "slug", "scenario", "version"):
        if not pack.get(key):
            errors.append(f"missing_{key}")
    target_min = (pack.get("blueprint") or {}).get("target_min") or {}
    for c in CORE_CONSTRUCTS:
        if c not in target_min:
            errors.append(f"missing_target_min_{c}")
    curve = pack.get("difficulty_curve") or []
    if len(curve) < 5:
        errors.append("difficulty_curve_too_short")
    if any((not isinstance(v, (int, float)) or v < 0 or v > 1) for v in curve):
        errors.append("difficulty_curve_values_invalid")
    if "forbid" not in ((pack.get("safety_profile") or {})):
        errors.append("missing_safety_forbid")
    fragments = pack.get("fragments")
    if not isinstance(fragments, list):
        errors.append("fragments_must_be_list")
    else:
        for idx, frag in enumerate(fragments):
            if not isinstance(frag, dict):
                errors.append(f"fragment_{idx}_invalid")
                continue
            for key in ("id", "tags", "text"):
                if key not in frag:
                    errors.append(f"fragment_{idx}_missing_{key}")
    return (len(errors) == 0, errors)


def load_builtin_packs() -> list[dict]:
    packs = []
    for path in sorted(PACKS_DIR.glob("*.json")):
        pack = load_pack_file(str(path))
        valid, errors = validate_pack(pack)
        if valid:
            packs.append(pack)
        else:
            print(f"[scenario_packs] skipped {path.name}: {errors}")
    return packs


def seed_builtin_packs() -> None:
    for pack in load_builtin_packs():
        try:
            upsert_scenario_pack(pack)
        except Exception as exc:
            print(f"[scenario_packs] seed failed for {pack.get('id')}: {exc}")


def get_default_pack_for_scenario(scenario: str) -> dict:
    db_pack = get_active_scenario_pack_for_scenario(scenario)
    if db_pack and db_pack.get("pack_json"):
        return db_pack["pack_json"]
    for pack in load_builtin_packs():
        if pack.get("scenario") == scenario:
            return pack
    packs = load_builtin_packs()
    if packs:
        return packs[0]
    return {
        "id": f"{scenario}_fallback_v1",
        "slug": f"{scenario}-fallback",
        "version": "2026-05-01",
        "scenario": scenario,
        "title": f"{scenario} fallback",
        "description": "Fallback pack",
        "max_turns_default": 5,
        "prompt_version": "scene_schema_v3",
        "blueprint": {
            "target_min": {k: 1 for k in CORE_CONSTRUCTS},
            "scenario_priority": ["decisiveness"],
            "cooldown_turns": 2,
        },
        "difficulty_curve": [0.42, 0.50, 0.58, 0.66, 0.72],
        "variable_features": {
            "ambiguity": {"min": 0.2, "max": 0.85},
            "time_pressure": {"min": 0.2, "max": 0.95},
            "conflict_affordance": {"min": 0.35, "max": 0.8},
        },
        "safety_profile": {"forbid": ["clinical_advice", "hiring_fitness_claims"]},
        "fragments": [],
    }
