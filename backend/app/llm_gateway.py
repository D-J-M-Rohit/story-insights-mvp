import json
import uuid
from time import perf_counter

from .config import settings
from .circuit_breaker import get_provider_circuit_breaker
from .logging_config import log_event
from .metrics import (
    record_provider_call,
    record_provider_fallback,
    record_provider_tokens,
    record_scene_generation,
    record_validation_failure,
)
from .provider_health import provider_health_tracker
from .prompts import build_scene_prompt
from .scene_validation import validate_scene_against_policy

TRAIT_KEYS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]
circuit_breaker = get_provider_circuit_breaker(settings)


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


def _sentence_count(text: str) -> int:
    if not text:
        return 0
    parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
    return len(parts)


def _ensure_scene_sentence_window(text: str, min_sentences: int = 4, max_sentences: int = 5) -> str:
    base = (text or "").strip()
    if not base:
        base = "You are in a decision point with competing priorities."
    sentences = [p.strip() for p in base.replace("\n", " ").split(".") if p.strip()]
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    while len(sentences) < min_sentences:
        if len(sentences) == 1:
            sentences.append("You need to weigh tradeoffs with limited time.")
        elif len(sentences) == 2:
            sentences.append("Different stakeholders expect different outcomes.")
        elif len(sentences) == 3:
            sentences.append("Your choice will influence what happens next.")
        else:
            sentences.append("Consider both immediate impact and longer-term consequences.")
    return ". ".join(sentences) + "."


class LLMGateway:
    def generate_scene(self, session, history, turn, policy=None, pack=None, context_bundle=None):
        policy = policy or self.fallback_policy(session, turn, pack)
        pack = pack or {}
        context_bundle = context_bundle or {
            "context_version": "context_v1",
            "retrieved_fragments": [],
            "avoid_repetition": [],
            "history_summary": "",
            "recent_choices": [],
        }
        provider = (settings.LLM_PROVIDER or "mock").lower()
        model = self.model_snapshot(provider)
        fallback_reason = None
        started = perf_counter()
        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                fallback_reason = "missing_api_key"
                scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
            elif not circuit_breaker.allow_request(provider, model):
                fallback_reason = "circuit_open"
                scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
            else:
                scene = self.generate_openai_scene(session, history, turn, policy, pack, context_bundle=context_bundle)
        elif provider == "gemini":
            if not settings.GEMINI_API_KEY:
                fallback_reason = "missing_api_key"
                scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
            elif not circuit_breaker.allow_request(provider, model):
                fallback_reason = "circuit_open"
                scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
            else:
                scene = self.generate_gemini_scene(session, history, turn, policy, pack, context_bundle=context_bundle)
        else:
            scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
        normalized = self.normalize_scene(scene, session["id"], turn, policy, context_bundle)
        validation = validate_scene_against_policy(normalized, policy, pack, context_bundle=context_bundle)
        if not validation["valid"] and provider in {"openai", "gemini"}:
            retry_scene = self.generate_provider_scene(
                provider, session, history, turn, policy, pack, context_bundle=context_bundle, strict_retry=True
            )
            normalized = self.normalize_scene(retry_scene, session["id"], turn, policy, context_bundle)
            validation = validate_scene_against_policy(normalized, policy, pack, context_bundle=context_bundle)
        if not validation["valid"]:
            fallback_reason = "scene_validation_failed"
            record_validation_failure("scene_generation", "scene_validation_failed")
            fallback_scene = self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
            normalized = self.normalize_scene(fallback_scene, session["id"], turn, policy, context_bundle)
            validation = validate_scene_against_policy(normalized, policy, pack, context_bundle=context_bundle)
        if provider in {"openai", "gemini"}:
            if fallback_reason:
                circuit_breaker.record_failure(provider, model, fallback_reason)
            else:
                circuit_breaker.record_success(provider, model)
        latency_ms = int((perf_counter() - started) * 1000)
        status = "ok" if provider == "mock" else ("fallback" if fallback_reason else "ok")
        record_scene_generation(provider, model, status, latency_ms / 1000.0)
        record_provider_call(provider, model, status)
        if fallback_reason:
            record_provider_fallback(provider, model, fallback_reason)
        provider_health_tracker.record_event(
            provider=provider,
            model=model,
            status=status,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            error_type=None,
            input_tokens=None,
            output_tokens=None,
        )
        record_provider_tokens(provider, model, input_tokens=None, output_tokens=None)
        log_event(
            "scene_generation_completed",
            provider=provider,
            model=model,
            status_code=200,
            duration_ms=latency_ms,
            fallback_used=bool(fallback_reason),
            error_type=None if validation.get("valid") else "validation_failed",
        )
        normalized["_meta"] = {
            "validation": validation,
            "fallback_reason": fallback_reason,
            "latency_ms": latency_ms,
            "provider": provider,
            "model_snapshot": model,
        }
        return normalized

    def model_snapshot(self, provider: str) -> str:
        if provider == "openai":
            return settings.OPENAI_MODEL or "gpt-4.1-mini"
        if provider == "gemini":
            return settings.GEMINI_MODEL or "gemini-2.5-flash"
        return "mock"

    def fallback_policy(self, session, turn, pack=None):
        pack = pack or {}
        return {
            "target_construct": "decisiveness",
            "difficulty": 0.5,
            "ambiguity": 0.5,
            "time_pressure": 0.5,
            "conflict_affordance": 0.55,
            "prompt_template": "fallback::decisiveness::core_scene",
            "prompt_version": pack.get("prompt_version", "scene_schema_v3"),
            "scenario_pack_id": pack.get("id", f"{session.get('scenario', 'default')}_fallback_v1"),
            "policy_version": "policy_v1",
            "time_limit_sec": 45,
            "rationale": {"reason": "fallback"},
        }

    def generate_provider_scene(self, provider, session, history, turn, policy, pack, context_bundle=None, strict_retry=False):
        if provider == "openai":
            return self.generate_openai_scene(
                session, history, turn, policy, pack, context_bundle=context_bundle, strict_retry=strict_retry
            )
        if provider == "gemini":
            return self.generate_gemini_scene(
                session, history, turn, policy, pack, context_bundle=context_bundle, strict_retry=strict_retry
            )
        return self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)

    def generate_mock_scene(self, session, history, turn, policy=None, pack=None, context_bundle=None):
        policy = policy or self.fallback_policy(session, turn, pack)
        scenario = session.get("scenario", "workplace")
        target = policy.get("target_construct", "social")
        context_bundle = context_bundle or {}
        frag_candidates = context_bundle.get("retrieved_fragments") or []
        frag = (
            frag_candidates[0]["text"]
            if frag_candidates
            else "A time-sensitive issue emerges and stakeholders expect action."
        )
        scene_body = _ensure_scene_sentence_window(
            (
                f"{frag} "
                "You have partial information and need to make a practical choice now. "
                "People around you are looking for a clear signal on what to do next. "
                "The path you choose will shape both trust and outcomes for the next step."
            )
        )
        title = f"{scenario.title()} Decision Point {turn}"
        avoid = " ".join(context_bundle.get("avoid_repetition", []))
        if "previous scene title" in avoid.lower():
            title = f"{scenario.title()} Fresh Decision {turn}"
        base_traits = {
            "risk": 0.5,
            "social": 0.5,
            "empathy": 0.5,
            "decisiveness": 0.5,
            "emotional_regulation": 0.5,
        }
        low = 0.2
        mid = 0.5
        high = 0.8
        options = []
        for oid, level, text in [
            ("A", high, "Take rapid action with clear ownership and immediate communication."),
            ("B", low, "Delay action to collect more context and reduce immediate exposure."),
            ("C", mid, "Take a balanced step now, then reassess with team feedback."),
        ]:
            traits = dict(base_traits)
            traits[target] = level
            options.append({"id": oid, "text": text, "traits": traits, "construct_tags": [target]})
        return {
            "title": title,
            "scene": scene_body,
            "time_limit_sec": int(policy.get("time_limit_sec", 45)),
            "options": options,
            "scene_metadata": {
                "target_construct": target,
                "difficulty": policy.get("difficulty", 0.5),
                "ambiguity": policy.get("ambiguity", 0.5),
                "time_pressure": policy.get("time_pressure", 0.5),
                "conflict_affordance": policy.get("conflict_affordance", 0.5),
                "context_fragment_ids": [f.get("id") for f in frag_candidates if f.get("id")],
            },
        }

    def generate_openai_scene(self, session, history, turn, policy, pack, context_bundle=None, strict_retry=False):
        try:
            from openai import OpenAI

            prompt = build_scene_prompt(
                session["scenario"], turn, session["max_turns"], history, policy=policy, pack=pack, context_bundle=context_bundle
            )
            if strict_retry:
                prompt += "\nSTRICT RETRY: follow schema exactly, include required metadata and target construct spread."
            model = settings.OPENAI_MODEL or "gpt-4.1-mini"
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.responses.create(model=model, input=prompt)
            text = getattr(response, "output_text", None)
            if not text:
                text = str(response)
            return self.parse_scene_json(text)
        except Exception:
            return self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)

    def generate_gemini_scene(self, session, history, turn, policy, pack, context_bundle=None, strict_retry=False):
        try:
            from google import genai

            prompt = build_scene_prompt(
                session["scenario"], turn, session["max_turns"], history, policy=policy, pack=pack, context_bundle=context_bundle
            )
            if strict_retry:
                prompt += "\nSTRICT RETRY: follow schema exactly, include required metadata and target construct spread."
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL or "gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            return self.parse_scene_json(response.text)
        except Exception:
            return self.generate_mock_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)

    def parse_scene_json(self, text):
        if not text:
            raise ValueError("Empty LLM response")
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Malformed JSON response")
        return json.loads(text[start : end + 1])

    def normalize_scene(self, data, session_id, turn, policy, context_bundle=None):
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
        time_limit_sec = int(policy.get("time_limit_sec", data.get("time_limit_sec", 45) if isinstance(data, dict) else 45) or 45)
        inferred_meta = _infer_scene_metadata(normalized_opts, time_limit_sec, turn)
        scene_metadata = {
            **inferred_meta,
            "target_construct": policy.get("target_construct"),
            "difficulty": policy.get("difficulty", inferred_meta.get("difficulty")),
            "ambiguity": policy.get("ambiguity", inferred_meta.get("ambiguity")),
            "time_pressure": policy.get("time_pressure", inferred_meta.get("time_pressure")),
            "conflict_affordance": policy.get("conflict_affordance", inferred_meta.get("conflict_affordance")),
            "scenario_pack_id": policy.get("scenario_pack_id"),
            "prompt_version": policy.get("prompt_version"),
            "policy_version": policy.get("policy_version"),
            "context_version": (context_bundle or {}).get("context_version", "context_v1"),
            "context_fragment_ids": [
                f.get("id") for f in ((context_bundle or {}).get("retrieved_fragments") or []) if f.get("id")
            ],
        }
        if isinstance(data, dict) and isinstance(data.get("scene_metadata"), dict):
            merged = dict(scene_metadata)
            for k, v in data["scene_metadata"].items():
                if v is not None:
                    merged[k] = _clamp01(v) if isinstance(v, (int, float)) else v
            scene_metadata = merged
        return {
            "id": scene_id,
            "session_id": session_id,
            "turn": turn,
            "title": data.get("title", f"Decision Point {turn}") if isinstance(data, dict) else f"Decision Point {turn}",
            "scene": _ensure_scene_sentence_window(
                data.get("scene", "You face a choice with competing priorities.")
                if isinstance(data, dict)
                else "You face a choice with competing priorities."
            ),
            "time_limit_sec": time_limit_sec,
            "options": normalized_opts,
            "scene_metadata": scene_metadata,
        }
