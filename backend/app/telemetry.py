import json


def clamp(v, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return lo


def derive_dwell_from_hover_log(hover_log: list[dict]) -> dict:
    dwell = {"A": 0, "B": 0, "C": 0}
    active = {}
    for evt in hover_log or []:
        opt = evt.get("option_id")
        if opt not in dwell:
            continue
        t = float(evt.get("t_ms", 0) or 0)
        kind = evt.get("event") or "enter"
        if kind == "enter":
            active[opt] = t
        elif kind == "leave" and opt in active:
            dwell[opt] += max(0, int(t - active.pop(opt)))
    return dwell


def dominant_dwell_option(telemetry: dict) -> str | None:
    dwell = telemetry.get("hover_dwell_ms_by_option") or {}
    if not dwell:
        return None
    best = max(dwell.items(), key=lambda kv: float(kv[1] or 0))
    return best[0] if float(best[1] or 0) > 0 else None


def normalize_telemetry(raw: dict, time_limit_sec: int | float = 45) -> dict:
    raw = raw or {}
    out = {}
    out["latency_ms"] = max(0, int(float(raw.get("latency_ms", 0) or 0)))
    limit_ms = max(1, int(float(time_limit_sec or 45) * 1000))
    out["latency_ratio"] = round(clamp(out["latency_ms"] / limit_ms, 0, 2), 4)
    hover_log = raw.get("hover_log") or []
    if not isinstance(hover_log, list):
        hover_log = []
    hover_log = hover_log[:80]
    norm_log = []
    for e in hover_log:
        if not isinstance(e, dict):
            continue
        norm_log.append(
            {
                "event": e.get("event", "enter") if e.get("event") in {"enter", "leave"} else "enter",
                "option_id": str(e.get("option_id", "")),
                "t_ms": max(0, int(float(e.get("t_ms", 0) or 0))),
            }
        )
    out["hover_log"] = norm_log
    dwell = raw.get("hover_dwell_ms_by_option") or {}
    if not isinstance(dwell, dict) or not dwell:
        dwell = derive_dwell_from_hover_log(norm_log)
    out["hover_dwell_ms_by_option"] = {k: max(0, int(float(dwell.get(k, 0) or 0))) for k in ["A", "B", "C"]}
    out["hover_switch_count"] = max(0, int(float(raw.get("hover_switch_count", 0) or 0)))
    out["first_hovered_option_id"] = raw.get("first_hovered_option_id") or (norm_log[0]["option_id"] if norm_log else None)
    out["last_hovered_option_id"] = raw.get("last_hovered_option_id") or (norm_log[-1]["option_id"] if norm_log else None)
    out["timed_out"] = bool(raw.get("timed_out", False))
    out["focus_lost_count"] = max(0, int(float(raw.get("focus_lost_count", 0) or 0)))
    out["browser_focus_lost"] = bool(raw.get("browser_focus_lost", out["focus_lost_count"] > 0))
    view_order = raw.get("option_view_order") or []
    if not isinstance(view_order, list):
        view_order = []
    unique = []
    for x in view_order:
        if x in {"A", "B", "C"} and x not in unique:
            unique.append(x)
    if not unique:
        for evt in norm_log:
            oid = evt.get("option_id")
            if oid in {"A", "B", "C"} and oid not in unique:
                unique.append(oid)
    out["option_view_order"] = unique
    changed_intent = raw.get("changed_intent")
    if changed_intent is None:
        dominant = dominant_dwell_option(out)
        selected = raw.get("selected_option_id")
        if selected:
            out["changed_intent"] = bool((out["first_hovered_option_id"] and selected != out["first_hovered_option_id"]) or (dominant and selected != dominant))
        else:
            out["changed_intent"] = False
    else:
        out["changed_intent"] = bool(changed_intent)
    blob = json.dumps(out)
    if len(blob) > 16000:
        out.pop("hover_log", None)
    return out


def stress_signal(choice) -> float:
    t = choice.get("telemetry") or {}
    return clamp(
        0.35 * clamp(t.get("latency_ratio", 0.0))
        + 0.25 * (1.0 if t.get("timed_out") else 0.0)
        + 0.20 * min(float(t.get("hover_switch_count", 0) or 0) / 5.0, 1.0)
        + 0.20 * (1.0 if t.get("changed_intent") else 0.0)
    )


def engagement_signal(choice) -> float:
    t = choice.get("telemetry") or {}
    lr = float(t.get("latency_ratio", 0.0) or 0.0)
    timeout = bool(t.get("timed_out"))
    if timeout:
        reasonable = 0.0
    elif 0.15 <= lr <= 0.85:
        reasonable = 1.0
    elif lr < 0.15:
        reasonable = 0.5
    else:
        reasonable = 0.6
    switches = float(t.get("hover_switch_count", 0) or 0)
    if 1 <= switches <= 3:
        bounded = 1.0
    elif switches == 0:
        bounded = 0.5
    else:
        bounded = clamp(1.0 - ((switches - 3.0) / 5.0))
    return clamp(0.40 * (0.0 if timeout else 1.0) + 0.30 * reasonable + 0.30 * bounded)


def telemetry_summary_for_evidence(choices: list[dict]) -> dict:
    choices = choices or []
    completed = len(choices)
    if completed == 0:
        return {
            "completed": 0,
            "timeout_count": 0,
            "changed_intent_count": 0,
            "avg_latency_ratio": 0.0,
            "prolonged_hesitation_count": 0,
            "avg_hover_switch_count": 0.0,
            "avg_focus_lost_count": 0.0,
            "choices_after_65pct": 0,
            "dominant_dwell_switch_count": 0,
        }
    timeout_count = 0
    changed_intent_count = 0
    latency_ratios = []
    switches = []
    focus_losses = []
    choices_after_65pct = 0
    dominant_switch = 0
    for c in choices:
        t = c.get("telemetry") or {}
        lr = float(t.get("latency_ratio", 0.0) or 0.0)
        latency_ratios.append(lr)
        sw = float(t.get("hover_switch_count", 0.0) or 0.0)
        switches.append(sw)
        focus_losses.append(float(t.get("focus_lost_count", 0.0) or 0.0))
        if t.get("timed_out"):
            timeout_count += 1
        if t.get("changed_intent"):
            changed_intent_count += 1
        if lr > 0.65:
            choices_after_65pct += 1
        selected = c.get("option_id")
        dom = dominant_dwell_option(t)
        if selected and dom and selected != dom:
            dominant_switch += 1
    return {
        "completed": completed,
        "timeout_count": timeout_count,
        "changed_intent_count": changed_intent_count,
        "avg_latency_ratio": round(sum(latency_ratios) / completed, 4),
        "prolonged_hesitation_count": sum(1 for v in latency_ratios if v > 0.65),
        "avg_hover_switch_count": round(sum(switches) / completed, 4),
        "avg_focus_lost_count": round(sum(focus_losses) / completed, 4),
        "choices_after_65pct": choices_after_65pct,
        "dominant_dwell_switch_count": dominant_switch,
    }
