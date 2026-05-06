import json


def build_scene_prompt(scenario, turn, max_turns, history):
    concise_history = []
    for item in history[-3:]:
        concise_history.append(
            {
                "turn": item.get("turn"),
                "title": item.get("title"),
                "choice": item.get("selected_option"),
            }
        )
    schema = {
        "title": "string",
        "scene": "string",
        "time_limit_sec": 45,
        "scene_metadata": {
            "conflict_affordance": 0.0,
            "time_pressure": 0.0,
            "ambiguity": 0.0,
            "social_pressure": 0.0,
            "risk_salience": 0.0,
            "difficulty": 0.0,
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
        f"Scenario: {scenario}\n"
        f"Turn: {turn}\n"
        f"Max turns: {max_turns}\n"
        f"Previous summary: {json.dumps(concise_history)}\n\n"
        "Rules:\n"
        "- Realistic, short, decision-focused scene.\n"
        "- Exactly 3 options.\n"
        "- Option IDs must be A, B, C.\n"
        "- traits must include risk, social, empathy, decisiveness, emotional_regulation.\n"
        "- Each trait value must be a float between 0 and 1.\n"
        "- Include scene_metadata with floats 0..1 for conflict_affordance, time_pressure, ambiguity, social_pressure, risk_salience, difficulty.\n"
        "- Each option may include quality (0..1) and quality_dimensions (safety, ethics, effectiveness, long_term_utility).\n"
        "- LLM must generate scene/options only and must not score the user.\n\n"
        f"Required JSON schema example: {json.dumps(schema)}"
    )
