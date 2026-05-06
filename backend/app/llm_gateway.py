import json
import uuid

from .config import settings
from .prompts import build_scene_prompt

TRAIT_KEYS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]


def _clamp01(x):
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _quality_from_traits(traits):
    r = _clamp01(traits.get("risk", 0.5))
    emp = _clamp01(traits.get("empathy", 0.5))
    dec = _clamp01(traits.get("decisiveness", 0.5))
    emo = _clamp01(traits.get("emotional_regulation", 0.5))
    qdims = {
        "safety": _clamp01(1.0 - r),
        "ethics": emp,
        "effectiveness": dec,
        "long_term_utility": emo,
    }
    q = sum(qdims.values()) / 4.0
    return round(q, 3), {k: round(v, 3) for k, v in qdims.items()}


def _infer_scene_metadata(options, time_limit_sec, turn):
    risks = [_clamp01(o.get("traits", {}).get("risk", 0.5)) for o in options]
    emps = [_clamp01(o.get("traits", {}).get("empathy", 0.5)) for o in options]
    socials = [_clamp01(o.get("traits", {}).get("social", 0.5)) for o in options]
    spread_re = (max(risks) - min(risks) + max(emps) - min(emps)) / 2.0
    conflict_affordance = _clamp01(0.35 + 0.55 * spread_re)
    ambiguity = _clamp01(0.3 + 0.08 * float(turn) + 0.22 * spread_re)
    social_pressure = _clamp01(0.38 + 0.52 * (max(socials) - min(socials)))
    risk_salience = _clamp01(0.38 + 0.55 * (max(risks) - min(risks)))
    difficulty = _clamp01(0.32 + 0.06 * float(turn) + 0.38 * spread_re)

    if time_limit_sec <= 25:
        time_pressure = 1.0
    elif time_limit_sec <= 40:
        time_pressure = 0.75
    elif time_limit_sec <= 60:
        time_pressure = 0.50
    else:
        time_pressure = 0.25

    return {
        "conflict_affordance": conflict_affordance,
        "time_pressure": time_pressure,
        "ambiguity": ambiguity,
        "social_pressure": social_pressure,
        "risk_salience": risk_salience,
        "difficulty": difficulty,
    }


class LLMGateway:
    def generate_scene(self, session, history, turn):
        provider = (settings.LLM_PROVIDER or "mock").lower()
        if provider == "openai":
            scene = self.generate_openai_scene(session, history, turn)
            return self.normalize_scene(scene, session["id"], turn)
        if provider == "gemini":
            scene = self.generate_gemini_scene(session, history, turn)
            return self.normalize_scene(scene, session["id"], turn)
        scene = self.generate_mock_scene(session, history, turn)
        return self.normalize_scene(scene, session["id"], turn)

    def generate_mock_scene(self, session, history, turn):
        scenario = session.get("scenario", "workplace")
        templates = {
            "workplace": [
                ("The Late Alert", "A critical bug alert arrives 20 minutes before a stakeholder demo."),
                ("Credit and Conflict", "A teammate takes public credit for your core work in a meeting."),
                ("Deadline Drift", "A deliverable slips and leadership asks for immediate recovery options."),
            ],
            "school": [
                ("Group Project Pivot", "Your team realizes the project plan no longer matches rubric expectations."),
                ("Exam Rumor", "Classmates share leaked exam topics and ask if you want in."),
                ("Mentor Feedback", "Your advisor gives harsh feedback one day before submission."),
            ],
            "emergency": [
                ("Crowded Exit", "An alarm triggers in a crowded venue and people panic near an exit."),
                ("Resource Triage", "Two urgent requests arrive but only one team is immediately available."),
                ("Comms Breakdown", "Network failure blocks normal communication during a field response."),
            ],
        }
        picked = templates.get(scenario, templates["workplace"])[(turn - 1) % 3]
        base = ((turn * 37) % 100) / 100
        return {
            "title": picked[0],
            "scene": picked[1],
            "time_limit_sec": 45,
            "options": [
                {
                    "id": "A",
                    "text": "Act immediately with a decisive plan and notify key people.",
                    "traits": {
                        "risk": round(min(base + 0.25, 1), 2),
                        "social": 0.7,
                        "empathy": 0.55,
                        "decisiveness": 0.88,
                        "emotional_regulation": 0.65,
                    },
                    "construct_tags": ["decisiveness", "social"],
                },
                {
                    "id": "B",
                    "text": "Pause to gather input and align group consensus before moving.",
                    "traits": {
                        "risk": 0.35,
                        "social": 0.82,
                        "empathy": 0.78,
                        "decisiveness": 0.5,
                        "emotional_regulation": 0.75,
                    },
                    "construct_tags": ["social", "empathy"],
                },
                {
                    "id": "C",
                    "text": "Contain immediate downside first, then communicate in structured steps.",
                    "traits": {
                        "risk": 0.45,
                        "social": 0.58,
                        "empathy": 0.62,
                        "decisiveness": 0.7,
                        "emotional_regulation": 0.84,
                    },
                    "construct_tags": ["emotional_regulation", "risk"],
                },
            ],
        }

    def generate_openai_scene(self, session, history, turn):
        try:
            from openai import OpenAI

            prompt = build_scene_prompt(session["scenario"], turn, session["max_turns"], history)
            model = settings.OPENAI_MODEL or "gpt-4.1-mini"
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.responses.create(model=model, input=prompt)
            text = getattr(response, "output_text", None)
            if not text:
                text = str(response)
            return self.parse_scene_json(text)
        except Exception:
            return self.generate_mock_scene(session, history, turn)

    def generate_gemini_scene(self, session, history, turn):
        try:
            from google import genai

            prompt = build_scene_prompt(session["scenario"], turn, session["max_turns"], history)
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL or "gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            return self.parse_scene_json(response.text)
        except Exception:
            return self.generate_mock_scene(session, history, turn)

    def parse_scene_json(self, text):
        if not text:
            raise ValueError("Empty LLM response")
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Malformed JSON response")
        return json.loads(text[start : end + 1])

    def normalize_scene(self, data, session_id, turn):
        scene_id = str(uuid.uuid4())
        options_in = data.get("options", []) if isinstance(data, dict) else []
        ids = ["A", "B", "C"]
        normalized_opts = []
        for idx, oid in enumerate(ids):
            src = options_in[idx] if idx < len(options_in) else {}
            traits = {}
            src_traits = src.get("traits", {}) if isinstance(src, dict) else {}
            for key in TRAIT_KEYS:
                val = src_traits.get(key, 0.5)
                try:
                    val = float(val)
                except Exception:
                    val = 0.5
                traits[key] = max(0.0, min(1.0, val))
            q, qdims = _quality_from_traits(traits)
            if isinstance(src, dict) and isinstance(src.get("quality_dimensions"), dict):
                for k in ("safety", "ethics", "effectiveness", "long_term_utility"):
                    if k in src["quality_dimensions"] and src["quality_dimensions"][k] is not None:
                        qdims[k] = round(_clamp01(src["quality_dimensions"][k]), 3)
                q = round(sum(qdims.values()) / 4.0, 3)
            elif isinstance(src, dict) and src.get("quality") is not None:
                q = round(_clamp01(src.get("quality")), 3)
            normalized_opts.append(
                {
                    "id": oid,
                    "text": src.get("text", f"Option {oid} action") if isinstance(src, dict) else f"Option {oid} action",
                    "traits": traits,
                    "construct_tags": src.get("construct_tags", [oid.lower()]) if isinstance(src, dict) else [oid.lower()],
                    "quality": q,
                    "quality_dimensions": qdims,
                }
            )
        time_limit_sec = int(data.get("time_limit_sec", 45) or 45) if isinstance(data, dict) else 45
        inferred_meta = _infer_scene_metadata(normalized_opts, time_limit_sec, turn)
        scene_metadata = inferred_meta
        if isinstance(data, dict) and isinstance(data.get("scene_metadata"), dict):
            merged = dict(inferred_meta)
            for k, v in data["scene_metadata"].items():
                if v is not None:
                    merged[k] = _clamp01(v)
            scene_metadata = merged
        return {
            "id": scene_id,
            "session_id": session_id,
            "turn": turn,
            "title": data.get("title", f"Decision Point {turn}") if isinstance(data, dict) else f"Decision Point {turn}",
            "scene": data.get("scene", "You face a choice with competing priorities.")
            if isinstance(data, dict)
            else "You face a choice with competing priorities.",
            "time_limit_sec": time_limit_sec,
            "options": normalized_opts,
            "scene_metadata": scene_metadata,
        }
