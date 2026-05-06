FORBIDDEN_TERMS = [
    "diagnosis",
    "clinical",
    "mental disorder",
    "fit for job",
    "hiring decision",
    "self-harm instructions",
    "sexual",
    "illegal",
]

REQUIRED_TRAITS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]


def validate_scene_against_policy(scene: dict, policy: dict, pack: dict) -> dict:
    errors = []
    warnings = []
    if not scene.get("title"):
        errors.append("missing_title")
    if not scene.get("scene"):
        errors.append("missing_scene_text")
    opts = scene.get("options") or []
    if len(opts) != 3:
        errors.append("options_must_be_exactly_3")
    ids = [o.get("id") for o in opts]
    if ids != ["A", "B", "C"]:
        errors.append("option_ids_must_be_A_B_C")
    target = policy.get("target_construct")
    text_blob = " ".join([scene.get("title", ""), scene.get("scene", ""), *[str(o.get("text", "")) for o in opts]]).lower()
    for bad in FORBIDDEN_TERMS:
        if bad in text_blob:
            errors.append(f"forbidden_term:{bad}")

    target_vals = []
    target_tag_present = False
    for idx, o in enumerate(opts):
        if not o.get("text"):
            errors.append(f"option_{idx}_missing_text")
        traits = o.get("traits") or {}
        for trait in REQUIRED_TRAITS:
            if trait not in traits:
                errors.append(f"option_{idx}_missing_trait_{trait}")
                continue
            try:
                value = float(traits.get(trait))
            except Exception:
                errors.append(f"option_{idx}_trait_{trait}_not_float")
                continue
            if value < 0 or value > 1:
                errors.append(f"option_{idx}_trait_{trait}_out_of_range")
        if target in traits:
            target_vals.append(float(traits.get(target, 0.5)))
        tags = o.get("construct_tags") or []
        if target in tags:
            target_tag_present = True

    if len(target_vals) == 3 and (max(target_vals) - min(target_vals) < 0.25):
        errors.append("target_trait_spread_too_small")
    if not target_tag_present:
        errors.append("target_construct_not_in_construct_tags")

    meta = scene.get("scene_metadata")
    if not isinstance(meta, dict):
        errors.append("missing_scene_metadata")
        meta = {}
    if meta.get("target_construct") != target:
        errors.append("target_construct_mismatch")

    def within(field: str, tol: float):
        if field not in meta:
            errors.append(f"missing_metadata_{field}")
            return
        if abs(float(meta[field]) - float(policy.get(field, 0.0))) > tol:
            errors.append(f"{field}_out_of_policy_tolerance")

    within("difficulty", 0.15)
    within("ambiguity", 0.20)
    within("time_pressure", 0.20)
    within("conflict_affordance", 0.20)
    time_limit = int(scene.get("time_limit_sec", 0) or 0)
    if time_limit != int(policy.get("time_limit_sec", time_limit)) and time_limit not in [25, 35, 45, 60, 75]:
        errors.append("time_limit_invalid")

    if not errors and not pack:
        warnings.append("pack_missing_validation_soft")
    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
