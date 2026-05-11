import math


# ----------------------------
# Basic helpers
# ----------------------------

def clamp(v, lo=0.0, hi=1.0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def clamp100(v):
    return round(max(0.0, min(100.0, float(v))), 2)


def avg(values, default=0.0):
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else default


def weighted_avg(values, weights=None, default=0.0):
    if not values:
        return default

    if not weights:
        return avg(values, default)

    total_w = 0.0
    total = 0.0

    for v, w in zip(values, weights):
        if v is None:
            continue
        w = max(0.0, float(w or 0.0))
        total += float(v) * w
        total_w += w

    return total / total_w if total_w > 0 else default


def variance(values):
    if not values:
        return 0.0
    m = avg(values)
    return avg([(float(v) - m) ** 2 for v in values])


def normalized_entropy(values_by_key):
    """
    Returns 0..1.
    0 means all dwell on one option.
    1 means dwell evenly spread across options.
    """
    if not isinstance(values_by_key, dict) or len(values_by_key) < 2:
        return 0.0

    vals = [max(0.0, float(v or 0.0)) for v in values_by_key.values()]
    total = sum(vals)

    if total <= 0:
        return 0.0

    probs = [v / total for v in vals if v > 0]
    entropy = -sum(p * math.log(p) for p in probs)
    max_entropy = math.log(len(vals))

    return clamp(entropy / max_entropy if max_entropy > 0 else 0.0)


def shrunk_0_100(raw_0_1, evidence_count, prior=0.50, prior_strength=4.0):
    """
    Pulls tiny samples toward 50.
    This avoids overconfident 5-turn reports.
    """
    raw_0_1 = clamp(raw_0_1)
    n = max(0.0, float(evidence_count or 0.0))

    if n <= 0:
        return prior * 100.0

    value = ((raw_0_1 * n) + (prior * prior_strength)) / (n + prior_strength)
    return value * 100.0


def confidence_band(score, evidence_count):
    """
    Simple confidence band.
    This is not a validated psychometric standard error.
    It only communicates that fewer scenes means lower confidence.
    """
    n = max(0, int(evidence_count or 0))

    if n <= 0:
        width = 35
    elif n < 3:
        width = 28
    elif n < 6:
        width = 20
    elif n < 10:
        width = 14
    else:
        width = 10

    return clamp100(score - width), clamp100(score + width)


def interpretation_status(evidence_count):
    n = int(evidence_count or 0)

    if n < 3:
        return "insufficient_evidence"
    if n < 8:
        return "exploratory"
    return "demo_confidence_only"


# ----------------------------
# Choice / scene helpers
# ----------------------------

TRAIT_KEYS = [
    "risk",
    "social",
    "empathy",
    "decisiveness",
    "emotional_regulation",
]


def get_telemetry(choice):
    return choice.get("telemetry") or {}


def get_scene_meta(choice):
    """
    Supports multiple possible names so the scorer works with your current schema
    and future richer schemas.
    """
    return (
        choice.get("scene_metadata")
        or choice.get("scene_meta")
        or choice.get("metadata")
        or {}
    )


def get_options(choice):
    """
    For better scoring, store all options shown in the scene with the choice record.
    Supported field names:
    - options
    - scene_options
    - all_options

    If not available, scorer falls back to selected option only.
    """
    options = (
        choice.get("options")
        or choice.get("scene_options")
        or choice.get("all_options")
        or []
    )

    return options if isinstance(options, list) else []


def get_selected_option(choice):
    option_id = choice.get("option_id") or choice.get("selected_option_id")
    options = get_options(choice)

    for option in options:
        if option.get("id") == option_id:
            return option

    return {
        "id": option_id,
        "text": choice.get("option_text", ""),
        "traits": choice.get("traits", {}) or {},
        "quality": choice.get("quality", None),
        "quality_dimensions": choice.get("quality_dimensions", None),
    }


def trait_value(option_or_choice, key, default=0.5):
    traits = option_or_choice.get("traits", {}) or {}

    try:
        return clamp(float(traits.get(key, default)))
    except (TypeError, ValueError):
        return clamp(default)


def selected_trait(choice, key, default=0.5):
    selected = get_selected_option(choice)
    return trait_value(selected, key, default)


def relative_trait(choice, key, default=0.5):
    """
    Scores selected option relative to options in the same scene.

    Example:
    If all options are high risk, selecting the least risky option should not
    produce a high risk-tolerance score.
    """
    selected = get_selected_option(choice)
    selected_val = trait_value(selected, key, default)
    options = get_options(choice)

    vals = [trait_value(o, key, None) for o in options if isinstance(o, dict)]
    vals = [v for v in vals if v is not None]

    if len(vals) < 2:
        return selected_val

    lo = min(vals)
    hi = max(vals)

    if abs(hi - lo) < 1e-9:
        return selected_val

    return clamp((selected_val - lo) / (hi - lo))


def option_quality(option_or_choice):
    """
    Preferred schema:
    quality: 0..1

    Better schema:
    quality_dimensions: {
        "safety": 0..1,
        "ethics": 0..1,
        "effectiveness": 0..1,
        "long_term_utility": 0..1
    }

    If absent, return neutral 0.5.
    """
    qd = option_or_choice.get("quality_dimensions")

    if isinstance(qd, dict):
        dims = [
            qd.get("safety"),
            qd.get("ethics"),
            qd.get("effectiveness"),
            qd.get("long_term_utility"),
        ]
        dims = [clamp(v) for v in dims if v is not None]

        if dims:
            return avg(dims, 0.5)

    q = option_or_choice.get("quality")

    if isinstance(q, dict):
        dims = [clamp(v) for v in q.values() if v is not None]
        return avg(dims, 0.5) if dims else 0.5

    if q is not None:
        return clamp(q)

    return 0.5


def selected_quality(choice):
    return option_quality(get_selected_option(choice))


def latency_ratio(choice):
    telemetry = get_telemetry(choice)

    try:
        latency_ms = float(telemetry.get("latency_ms", 0.0) or 0.0)
    except (TypeError, ValueError):
        latency_ms = 0.0

    try:
        limit_sec = float(choice.get("time_limit_sec", 45) or 45)
    except (TypeError, ValueError):
        limit_sec = 45.0

    if limit_sec <= 0:
        return 0.0

    return clamp(latency_ms / (limit_sec * 1000.0), 0.0, 2.0)


def timeout_flag(choice):
    return 1.0 if get_telemetry(choice).get("timed_out") else 0.0


def hover_switch_count(choice):
    telemetry = get_telemetry(choice)

    try:
        return max(0.0, float(telemetry.get("hover_switch_count", 0.0) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def hover_dwell_entropy(choice):
    telemetry = get_telemetry(choice)
    dwell = (
        telemetry.get("hover_dwell_ms_by_option")
        or telemetry.get("dwell_ms_by_option")
        or telemetry.get("dwell")
        or {}
    )
    return normalized_entropy(dwell)


def dominant_option_before_commit(choice):
    telemetry = get_telemetry(choice)

    direct = telemetry.get("dominant_option_before_commit")
    if direct:
        return direct

    dwell = (
        telemetry.get("hover_dwell_ms_by_option")
        or telemetry.get("dwell_ms_by_option")
        or {}
    )

    if isinstance(dwell, dict) and dwell:
        return max(dwell.items(), key=lambda x: float(x[1] or 0.0))[0]

    return None


def late_switch_flag(choice):
    telemetry = get_telemetry(choice)

    if telemetry.get("changed_intent"):
        return 1.0

    dominant = dominant_option_before_commit(choice)
    selected = choice.get("option_id") or choice.get("selected_option_id")

    if dominant and selected and dominant != selected:
        return 1.0

    return 0.0


def conflict_affordance(choice):
    """
    How much this scene is designed to reveal conflict.
    Prefer explicit scene metadata from your scenario generator.
    """
    meta = get_scene_meta(choice)

    if "conflict_affordance" in meta:
        return clamp(meta.get("conflict_affordance"))

    if "ambiguity" in meta:
        return clamp(meta.get("ambiguity"))

    return 0.5


def time_pressure(choice):
    """
    Prefer explicit scene metadata. Fall back to time limit.
    """
    meta = get_scene_meta(choice)

    if "time_pressure" in meta:
        return clamp(meta.get("time_pressure"))

    try:
        limit_sec = float(choice.get("time_limit_sec", 45) or 45)
    except (TypeError, ValueError):
        limit_sec = 45.0

    if limit_sec <= 25:
        return 1.0
    if limit_sec <= 40:
        return 0.75
    if limit_sec <= 60:
        return 0.50
    return 0.25


# ----------------------------
# Item-level evidence
# ----------------------------

def cdi_item_score(choice):
    """
    Conflict evidence for one scene.

    Stronger than old version because it combines:
    - latency pressure
    - dwell spread across options
    - hover switching
    - late switch / changed intent
    """
    lr = latency_ratio(choice)

    # Starts counting hesitation after 35% of the time limit.
    latency_conflict = clamp((lr - 0.35) / 0.65)

    dwell_conflict = hover_dwell_entropy(choice)

    # Log scale prevents huge switch counts from dominating.
    switch_conflict = clamp(math.log1p(hover_switch_count(choice)) / math.log1p(5.0))

    late_switch = late_switch_flag(choice)

    return clamp(
        0.30 * latency_conflict
        + 0.25 * dwell_conflict
        + 0.25 * switch_conflict
        + 0.20 * late_switch
    )


def adaptive_item_score(choice):
    """
    Decision effectiveness for one scene.

    This is not only speed. It uses:
    - option quality
    - not timing out
    - reasonable speed
    """
    timed_out = timeout_flag(choice)
    lr = clamp(latency_ratio(choice), 0.0, 1.0)
    quality = selected_quality(choice)

    if timed_out:
        return 0.0

    speed_component = 1.0 - lr

    return clamp(
        0.60 * quality
        + 0.25 * speed_component
        + 0.15 * (1.0 - timed_out)
    )


def recovery_score(items):
    """
    Compares early vs late adaptive performance.
    Stable or improving behavior scores higher.
    """
    if len(items) < 2:
        return 0.5

    mid = max(1, len(items) // 2)
    early = avg(items[:mid], 0.5)
    late = avg(items[mid:], early)

    return clamp(0.5 + (late - early) / 2.0)


def engagement_hover_quality(avg_switches):
    """
    Engagement should not mean unlimited hovering.
    Too little interaction may mean low engagement.
    Too much may mean confusion or interface noise.
    """
    if avg_switches <= 0:
        return 0.35

    if 0.5 <= avg_switches <= 3.0:
        return 1.0

    if avg_switches < 0.5:
        return clamp(avg_switches / 0.5)

    return clamp(1.0 - ((avg_switches - 3.0) / 5.0))


def effort_latency_quality(ratios):
    """
    Very fast responses may be careless.
    Extremely late responses may indicate overload or distraction.
    """
    if not ratios:
        return 0.0

    qualities = []

    for r in ratios:
        if 0.15 <= r <= 0.85:
            qualities.append(1.0)
        elif r < 0.15:
            qualities.append(0.45)
        elif r <= 1.0:
            qualities.append(0.70)
        else:
            qualities.append(0.25)

    return avg(qualities, 0.0)


# ----------------------------
# Feature builder
# ----------------------------

def make_feature(name, key, raw_0_1, evidence_count, description, shrink=True):
    if shrink:
        score = shrunk_0_100(raw_0_1, evidence_count)
    else:
        score = clamp(raw_0_1) * 100.0

    low, high = confidence_band(score, evidence_count)

    return {
        "name": name,
        "key": key,
        "score": clamp100(score),
        "raw_score": clamp100(clamp(raw_0_1) * 100.0),
        "evidence_count": int(evidence_count or 0),
        "confidence_low": low,
        "confidence_high": high,
        "interpretation_status": interpretation_status(evidence_count),
        "description": description,
    }


# ----------------------------
# Main scorer
# ----------------------------

def score_session(session, choices):
    max_turns = int(session.get("max_turns", 20) or 20)
    choices = choices or []
    completed = len(choices)

    if max_turns <= 0:
        max_turns = 20

    completed_ratio = clamp(completed / max_turns)

    # No evidence case: avoid fake high resilience.
    if completed == 0:
        empty_features = [
            make_feature("Risk / Low-Empathy Signal", "psychoticism_proxy", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Social Assertiveness Signal", "extraversion_proxy", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Stress-Reactivity Signal", "neuroticism_proxy", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Decision Conflict Index", "cdi", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Adaptive Decision-Making Quotient", "adq", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Relative Risk Preference", "risk_tolerance", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Social Orientation", "social_influence_sensitivity", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Time Pressure Resilience", "time_pressure_resilience", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Contextual Consistency", "consistency", 0.5, 0, "Insufficient evidence.", True),
            make_feature("Engagement Quality", "engagement", 0.0, 0, "No completed choices were recorded.", False),
        ]

        return {
            "session_id": session.get("id"),
            "summary": "This report is experimental and should not be treated as a clinical, hiring, or diagnostic assessment.",
            "features": empty_features,
            "pen": [
                {"name": "Risk / Low-Empathy Signal", "score": 50.0},
                {"name": "Social Assertiveness Signal", "score": 50.0},
                {"name": "Stress-Reactivity Signal", "score": 50.0},
            ],
            "choices": choices,
        }

    # Relative trait evidence
    rel_risks = [relative_trait(c, "risk") for c in choices]
    rel_socials = [relative_trait(c, "social") for c in choices]
    rel_empathies = [relative_trait(c, "empathy") for c in choices]
    rel_decisives = [relative_trait(c, "decisiveness") for c in choices]
    rel_emos = [relative_trait(c, "emotional_regulation") for c in choices]

    # Quality and timing evidence
    latency_ratios = [latency_ratio(c) for c in choices]
    timeouts = [timeout_flag(c) for c in choices]
    switches = [hover_switch_count(c) for c in choices]

    # CDI: weighted toward conflict-affording scenes
    cdi_items = [cdi_item_score(c) for c in choices]
    cdi_weights = [conflict_affordance(c) for c in choices]
    cdi_raw = weighted_avg(cdi_items, cdi_weights, 0.5)

    # ADQ: focus on high-pressure scenes
    pressure_weights = [time_pressure(c) for c in choices]
    pressure_choices = [
        (c, w) for c, w in zip(choices, pressure_weights)
        if w >= 0.5
    ]

    if pressure_choices:
        pressure_items = [adaptive_item_score(c) for c, _ in pressure_choices]
        pressure_item_weights = [w for _, w in pressure_choices]
        pressure_timeouts = [timeout_flag(c) for c, _ in pressure_choices]
    else:
        pressure_items = [adaptive_item_score(c) for c in choices]
        pressure_item_weights = pressure_weights
        pressure_timeouts = timeouts

    quality_under_pressure = weighted_avg(pressure_items, pressure_item_weights, 0.5)
    timeout_rate_pressure = avg(pressure_timeouts, 0.0)
    recovery = recovery_score(pressure_items)

    adq_raw = clamp(
        0.45 * quality_under_pressure
        + 0.30 * (1.0 - timeout_rate_pressure)
        + 0.25 * recovery
    )

    # Other interpretable scores
    risk_tolerance_raw = avg(rel_risks, 0.5)
    social_orientation_raw = avg(rel_socials, 0.5)

    avg_latency_ratio = avg([clamp(r, 0.0, 1.0) for r in latency_ratios], 1.0)
    timeout_rate = avg(timeouts, 0.0)

    time_pressure_resilience_raw = clamp(
        0.65 * (1.0 - timeout_rate)
        + 0.35 * (1.0 - avg_latency_ratio)
    )

    # Consistency should be about stability of profile, not raw identical answers.
    profile_variance = avg(
        [
            variance(rel_risks),
            variance(rel_socials),
            variance(rel_empathies),
            variance(rel_decisives),
            variance(rel_emos),
        ],
        0.0,
    )

    contextual_consistency_raw = clamp(1.0 - (math.sqrt(profile_variance) / 0.5))

    hover_quality = engagement_hover_quality(avg(switches, 0.0))
    non_timeout_ratio = 1.0 - timeout_rate
    effort_quality = effort_latency_quality(latency_ratios)

    engagement_raw = clamp(
        0.40 * completed_ratio
        + 0.25 * non_timeout_ratio
        + 0.20 * effort_quality
        + 0.15 * hover_quality
    )

    # Safer PEN-style signals.
    # These are descriptive signals, not clinical personality claims.
    psychoticism_raw = clamp(
        0.50 * avg(rel_risks, 0.5)
        + 0.50 * (1.0 - avg(rel_empathies, 0.5))
    )

    extraversion_raw = clamp(
        0.50 * avg(rel_socials, 0.5)
        + 0.50 * avg(rel_decisives, 0.5)
    )

    neuroticism_raw = clamp(
        0.55 * cdi_raw
        + 0.45 * (1.0 - avg(rel_emos, 0.5))
    )

    evidence_count = completed
    pressure_evidence_count = len(pressure_choices) if pressure_choices else completed

    features = [
        make_feature(
            "Risk / Low-Empathy Signal",
            "psychoticism_proxy",
            psychoticism_raw,
            evidence_count,
            "PEN-style descriptive signal estimated from relative risk preference and lower relative empathy. Not a clinical psychoticism measure.",
        ),
        make_feature(
            "Social Assertiveness Signal",
            "extraversion_proxy",
            extraversion_raw,
            evidence_count,
            "PEN-style descriptive signal estimated from relative social orientation and decisiveness.",
        ),
        make_feature(
            "Stress-Reactivity Signal",
            "neuroticism_proxy",
            neuroticism_raw,
            evidence_count,
            "PEN-style descriptive signal estimated from decision conflict and lower emotional-regulation choices.",
        ),
        make_feature(
            "Decision Conflict Index",
            "cdi",
            cdi_raw,
            evidence_count,
            "Conflict signal derived from hesitation, dwell spread, hover switching, and late intent change, weighted by conflict-affording scenes.",
        ),
        make_feature(
            "Adaptive Decision-Making Quotient",
            "adq",
            adq_raw,
            pressure_evidence_count,
            "Adaptability under pressure using option quality, timeout avoidance, speed efficiency, and recovery across pressured scenes.",
        ),
        make_feature(
            "Relative Risk Preference",
            "risk_tolerance",
            risk_tolerance_raw,
            evidence_count,
            "Average selected risk level relative to the alternatives shown in each scene.",
        ),
        make_feature(
            "Social Orientation",
            "social_influence_sensitivity",
            social_orientation_raw,
            evidence_count,
            "Average selected social orientation relative to the alternatives shown in each scene.",
        ),
        make_feature(
            "Time Pressure Resilience",
            "time_pressure_resilience",
            time_pressure_resilience_raw,
            pressure_evidence_count,
            "Ability to respond before timeout while avoiding consistently late responses.",
        ),
        make_feature(
            "Contextual Consistency",
            "consistency",
            contextual_consistency_raw,
            evidence_count,
            "Stability of relative decision profile across scenes. Lower values may also reflect changing context, not necessarily inconsistency.",
        ),
        make_feature(
            "Engagement Quality",
            "engagement",
            engagement_raw,
            evidence_count,
            "Participation quality based on completion, timeout behavior, reasonable latency, and bounded hover activity.",
            shrink=False,
        ),
    ]

    pen = [
        {
            "name": "Risk / Low-Empathy Signal",
            "key": "psychoticism_proxy",
            "score": clamp100(shrunk_0_100(psychoticism_raw, evidence_count)),
        },
        {
            "name": "Social Assertiveness Signal",
            "key": "extraversion_proxy",
            "score": clamp100(shrunk_0_100(extraversion_raw, evidence_count)),
        },
        {
            "name": "Stress-Reactivity Signal",
            "key": "neuroticism_proxy",
            "score": clamp100(shrunk_0_100(neuroticism_raw, evidence_count)),
        },
    ]

    summary = (
        "This report is experimental and should not be treated as a clinical, hiring, "
        "or diagnostic assessment. Scores are descriptive signals from a short branching-story "
        "session and should be interpreted with the evidence count and confidence band."
    )

    return {
        "session_id": session.get("id"),
        "summary": summary,
        "features": features,
        "pen": pen,
        "choices": choices,
    }
