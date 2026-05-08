import json


def build_scene_prompt(scenario, turn, max_turns, history, policy=None, pack=None, context_bundle=None):
    concise_history = []
    for item in history[-3:]:
        concise_history.append(
            {
                "turn": item.get("turn"),
                "title": item.get("title"),
                "choice": item.get("selected_option"),
            }
        )
    policy = policy or {}
    pack = pack or {}
    context_bundle = context_bundle or {
        "context_version": "context_v1",
        "history_summary": "",
        "recent_choices": [],
        "retrieved_fragments": [],
        "avoid_repetition": [],
    }
    schema = {
        "title": "string",
        "scene": "string",
        "time_limit_sec": int(policy.get("time_limit_sec", 45)),
        "scene_metadata": {
            "target_construct": policy.get("target_construct", "social"),
            "difficulty": float(policy.get("difficulty", 0.5)),
            "ambiguity": float(policy.get("ambiguity", 0.5)),
            "time_pressure": float(policy.get("time_pressure", 0.5)),
            "conflict_affordance": float(policy.get("conflict_affordance", 0.5)),
            "social_pressure": 0.0,
            "risk_salience": 0.0,
            "scenario_pack_id": policy.get("scenario_pack_id", ""),
            "prompt_version": policy.get("prompt_version", "scene_schema_v3"),
            "policy_version": policy.get("policy_version", "policy_v1")
            ,
            "context_fragment_ids": ["frag_id"]
        },
        "options": [
            {
                "id": "A",
                "text": "string",
                "traits": {
                    "risk": 0.0,
                    "social": 0.0,
                    "empathy": 0.0,
                    "decisiveness": 0.0,
                    "emotional_regulation": 0.0,
                },
                "construct_tags": ["social"],
                "quality": 0.0,
                "quality_dimensions": {
                    "safety": 0.0,
                    "ethics": 0.0,
                    "effectiveness": 0.0,
                    "long_term_utility": 0.0,
                },
            }
        ],
    }
    return (
        "You are generating scenes for a branching-story behavioral insights MVP. "
        "Return only valid JSON. No markdown.\n\n"
        f"Scenario Pack Title: {pack.get('title', 'Core Pack')}\n"
        f"Setting: {(pack.get('characteristic_features') or {}).get('setting', scenario)}\n"
        f"Scenario: {scenario}\n"
        f"Turn: {turn}\n"
        f"Max turns: {max_turns}\n"
        f"Target construct: {policy.get('target_construct', 'social')}\n"
        f"Difficulty: {policy.get('difficulty', 0.5)}\n"
        f"Ambiguity: {policy.get('ambiguity', 0.5)}\n"
        f"Time pressure: {policy.get('time_pressure', 0.5)}\n"
        f"Conflict affordance: {policy.get('conflict_affordance', 0.5)}\n"
        f"Required time_limit_sec: {policy.get('time_limit_sec', 45)}\n"
        f"Policy version: {policy.get('policy_version', 'policy_v1')}\n"
        f"Grounding Context ({context_bundle.get('context_version', 'context_v1')}):\n"
        f"- history_summary: {context_bundle.get('history_summary', '')}\n"
        f"- recent_choices: {json.dumps(context_bundle.get('recent_choices', []))}\n"
        f"- retrieved_fragments: {json.dumps(context_bundle.get('retrieved_fragments', []))}\n"
        f"- avoid_repetition: {json.dumps(context_bundle.get('avoid_repetition', []))}\n"
        f"- feedback_profile: {json.dumps((context_bundle.get('feedback_profile') or {}))}\n"
        f"Previous summary: {json.dumps(concise_history)}\n\n"
        f"Safety constraints: {json.dumps((pack.get('safety_profile') or {}).get('forbid', []))}\n"
        "Rules:\n"
        "- Realistic, decision-focused scene.\n"
        "- Scene body must be exactly 4 to 5 complete sentences.\n"
        "- Exactly 3 options.\n"
        "- Option IDs must be A, B, C.\n"
        "- Each option text must be at most 32 words.\n"
        "- traits must include risk, social, empathy, decisiveness, emotional_regulation.\n"
        "- Each trait value must be a float between 0 and 1.\n"
        "- Each option must include construct_tags; include target construct in at least one option.\n"
        "- Target construct must differ meaningfully across options.\n"
        "- Include scene_metadata mirroring policy values for target_construct, difficulty, ambiguity, time_pressure, conflict_affordance.\n"
        "- Include scene_metadata.context_fragment_ids list from relevant retrieved fragments.\n"
        "- Each option may include quality (0..1) and quality_dimensions (safety, ethics, effectiveness, long_term_utility).\n"
        "- Do not score the user.\n"
        "- Use retrieved fragments only as grounding material; do not copy them verbatim.\n"
        "- Do not contradict the previous story summary.\n"
        "- Do not repeat previous scene setups.\n"
        "- Presentation feedback hints may guide wording/clarity/tone only.\n"
        "- Do not change target construct, difficulty, option trait values, scoring logic, scenario-pack coverage, or validation thresholds.\n"
        "- Do not mention psychology, diagnosis, mental health, personality type, employability, or hiring fit.\n\n"
        f"Required JSON schema example: {json.dumps(schema)}"
    )
