import hashlib
import json
import random

CORE_CONSTRUCTS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]
POLICY_VERSION = "policy_v1"


def clamp(x, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo


def ema(prev, value, alpha=0.35):
    return clamp((1 - alpha) * float(prev) + alpha * float(value))


def telemetry_summary(choices) -> dict:
    if not choices:
        return {"stress_ema": 0.5, "engagement_ema": 0.5}
    stress = 0.5
    engage = 0.5
    for c in choices:
        t = c.get("telemetry") or {}
        tl_sec = float(c.get("time_limit_sec") or 45)
        latency_ratio = clamp(float(t.get("latency_ms") or 0) / max(tl_sec * 1000.0, 1.0), 0.0, 1.5)
        timeout = 1.0 if t.get("timed_out") else 0.0
        switches = clamp(float(t.get("hover_switch_count") or 0) / 5.0)
        changed_intent = 1.0 if t.get("changed_intent") else 0.0
        stress_signal = clamp(0.35 * clamp(latency_ratio) + 0.25 * timeout + 0.20 * switches + 0.20 * changed_intent)

        if timeout:
            reasonable_latency = 0.0
        elif 0.15 <= latency_ratio <= 0.85:
            reasonable_latency = 1.0
        elif latency_ratio < 0.15:
            reasonable_latency = 0.5
        else:
            reasonable_latency = 0.6
        switch_val = float(t.get("hover_switch_count") or 0.0)
        if 1.0 <= switch_val <= 3.0:
            bounded_hover = 1.0
        elif switch_val == 0:
            bounded_hover = 0.5
        else:
            bounded_hover = clamp(1.0 - ((switch_val - 3.0) / 5.0))
        non_timeout = 1.0 - timeout
        engagement_signal = clamp(0.40 * non_timeout + 0.30 * reasonable_latency + 0.30 * bounded_hover)

        stress = ema(stress, stress_signal)
        engage = ema(engage, engagement_signal)
    return {"stress_ema": round(stress, 3), "engagement_ema": round(engage, 3)}


def construct_counts(choices) -> dict:
    counts = {c: 0 for c in CORE_CONSTRUCTS}
    for ch in choices:
        meta = ch.get("scene_metadata") or {}
        target = meta.get("target_construct")
        if target in counts:
            counts[target] += 1
            continue
        tags = []
        if isinstance(ch.get("options"), list):
            selected = next((o for o in ch.get("options", []) if o.get("id") == ch.get("option_id")), None)
            tags = (selected or {}).get("construct_tags", []) or []
        tag = next((t for t in tags if t in counts), None)
        if tag:
            counts[tag] += 1
            continue
        traits = ch.get("traits") or {}
        if traits:
            best = max(CORE_CONSTRUCTS, key=lambda k: float(traits.get(k, 0.0)))
            counts[best] += 1
    return counts


def choose_construct(session, choices, pack, turn) -> str:
    counts = construct_counts(choices)
    telemetry = telemetry_summary(choices)
    stress_ema = telemetry["stress_ema"]
    target_min = ((pack.get("blueprint") or {}).get("target_min") or {k: 1 for k in CORE_CONSTRUCTS})
    turns_left = max(int(session.get("max_turns", 5)) - turn + 1, 1)
    recent = [((c.get("scene_metadata") or {}).get("target_construct")) for c in choices[-2:]]
    prev = recent[-1] if recent else None

    unmet = [c for c in CORE_CONSTRUCTS if counts[c] < int(target_min.get(c, 1))]
    if turn >= int(session.get("max_turns", 5)) and unmet:
        return max(unmet, key=lambda c: (int(target_min.get(c, 1)) - counts[c]) / turns_left)

    priorities = ((pack.get("blueprint") or {}).get("scenario_priority") or [])
    scores = {}
    for c in CORE_CONSTRUCTS:
        tm = max(int(target_min.get(c, 1)), 1)
        seen = counts[c]
        deficit = max(tm - seen, 0) / tm
        urgency = max(tm - seen, 0) / turns_left
        if c == prev and unmet:
            cooldown = 1.0
        elif c in recent:
            cooldown = 0.25
        else:
            cooldown = 0.0
        stress_fit = 0.0
        if stress_ema >= 0.60 and c in {"emotional_regulation", "decisiveness"}:
            stress_fit = 0.15
        elif stress_ema <= 0.40 and c in {"risk", "social"}:
            stress_fit = 0.10
        novelty = 0.10 if seen == 0 else 0.0
        priority = 0.08 if c in priorities else 0.0
        scores[c] = 0.42 * deficit + 0.15 * urgency + 0.15 * stress_fit + 0.10 * novelty + 0.08 * priority - 0.20 * cooldown

    best = max(scores.values())
    candidates = sorted([c for c, v in scores.items() if v >= (best - 0.08)])
    seed = f"{session.get('id')}:{turn}:{pack.get('version')}"
    return random.Random(seed).choice(candidates)


def choose_difficulty(session, choices, pack, turn) -> float:
    curve = pack.get("difficulty_curve") or [0.42, 0.50, 0.58, 0.66, 0.72]
    idx = min(max(turn - 1, 0), len(curve) - 1)
    base = float(curve[idx])
    telemetry = telemetry_summary(choices)
    raw = base - 0.12 * (telemetry["stress_ema"] - 0.50) + 0.08 * (telemetry["engagement_ema"] - 0.50)
    raw = clamp(raw, 0.30, 0.85)
    prev = None
    if choices:
        prev_meta = choices[-1].get("scene_metadata") or {}
        prev = prev_meta.get("difficulty")
    if prev is not None:
        prev = float(prev)
        if raw > prev + 0.12:
            raw = prev + 0.12
        if raw < prev - 0.12:
            raw = prev - 0.12
    return round(clamp(raw, 0.30, 0.85), 3)


def map_knobs(target_construct, difficulty, pack) -> dict:
    amb_bonus = {"social": 0.04, "empathy": 0.05, "risk": 0.00, "decisiveness": -0.02, "emotional_regulation": 0.03}
    conf_bonus = {"social": 0.06, "empathy": 0.04, "risk": 0.03, "decisiveness": 0.02, "emotional_regulation": 0.03}
    vf = pack.get("variable_features") or {}
    ambiguity = 0.18 + 0.55 * difficulty + amb_bonus.get(target_construct, 0.0)
    conflict = 0.32 + 0.48 * difficulty + conf_bonus.get(target_construct, 0.0)
    time_pressure = 0.15 + 0.80 * difficulty

    def apply_range(key, value):
        bounds = vf.get(key) or {}
        return clamp(value, float(bounds.get("min", 0.0)), float(bounds.get("max", 1.0)))

    return {
        "ambiguity": round(apply_range("ambiguity", ambiguity), 3),
        "conflict_affordance": round(apply_range("conflict_affordance", conflict), 3),
        "time_pressure": round(apply_range("time_pressure", time_pressure), 3),
    }


def map_time_pressure_to_limit(time_pressure) -> int:
    if time_pressure >= 0.80:
        return 25
    if time_pressure >= 0.65:
        return 35
    if time_pressure >= 0.50:
        return 45
    if time_pressure >= 0.35:
        return 60
    return 75


def build_policy_input(session, choices, pack, turn) -> dict:
    return {
        "session_id": session.get("id"),
        "scenario": session.get("scenario"),
        "max_turns": session.get("max_turns"),
        "turn": turn,
        "pack_id": pack.get("id"),
        "pack_version": pack.get("version"),
        "counts": construct_counts(choices),
        "telemetry": telemetry_summary(choices),
    }


def hash_policy_payload(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def decide_policy(session: dict, choices: list[dict], pack: dict, turn: int) -> dict:
    policy_input = build_policy_input(session, choices, pack, turn)
    target_construct = choose_construct(session, choices, pack, turn)
    difficulty = choose_difficulty(session, choices, pack, turn)
    knobs = map_knobs(target_construct, difficulty, pack)
    time_limit_sec = map_time_pressure_to_limit(knobs["time_pressure"])
    return {
        "target_construct": target_construct,
        "difficulty": difficulty,
        "ambiguity": knobs["ambiguity"],
        "time_pressure": knobs["time_pressure"],
        "conflict_affordance": knobs["conflict_affordance"],
        "prompt_template": f"{pack.get('slug', session.get('scenario', 'core'))}::{target_construct}::core_scene",
        "prompt_version": pack.get("prompt_version", "scene_schema_v3"),
        "scenario_pack_id": pack.get("id", f"{session.get('scenario', 'default')}_fallback_v1"),
        "policy_version": POLICY_VERSION,
        "time_limit_sec": time_limit_sec,
        "rationale": {
            "coverage_deficit": {
                c: max(((pack.get("blueprint", {}).get("target_min", {}).get(c, 1)) - construct_counts(choices)[c]), 0)
                for c in CORE_CONSTRUCTS
            },
            "seen_counts": construct_counts(choices),
            "stress_ema": policy_input["telemetry"]["stress_ema"],
            "engagement_ema": policy_input["telemetry"]["engagement_ema"],
            "difficulty_base": (pack.get("difficulty_curve") or [difficulty])[min(max(turn - 1, 0), len(pack.get("difficulty_curve") or [difficulty]) - 1)],
            "difficulty_adjusted": difficulty,
        },
    }
