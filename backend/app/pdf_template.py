"""Jinja2 HTML builder for print/PDF reports. All user-controlled strings are escaped."""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def fmt_score(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(n):
        return "-"
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:.1f}"


def fmt_date(value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return s


def fmt_duration(ms) -> str:
    if ms is None or ms == "":
        return "-"
    try:
        sec = float(ms) / 1000.0
    except (TypeError, ValueError):
        return "-"
    if math.isnan(sec):
        return "-"
    return f"{sec:.1f} sec"


def clamp_score(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, n))


def bucket_class(bucket_or_band: str | None) -> str:
    if not bucket_or_band:
        return "bucket-neutral"
    b = str(bucket_or_band).lower()
    if "below" in b or b == "low":
        return "bucket-low"
    if "above" in b or b == "high":
        return "bucket-high"
    if "within" in b or b == "balanced":
        return "bucket-balanced"
    return "bucket-neutral"


def construct_coverage(report: dict) -> dict[str, int]:
    keys = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"]
    counts = {k: 0 for k in keys}
    for ch in report.get("choices") or []:
        meta = ch.get("scene_metadata") or {}
        target = meta.get("target_construct")
        if target in counts:
            counts[target] += 1
    return counts


def _compact_key_signals(trait_buckets: list) -> str:
    if not trait_buckets:
        return ""
    labels = []
    for tb in trait_buckets:
        if not isinstance(tb, dict):
            continue
        lab = tb.get("label")
        if isinstance(lab, str) and lab.strip():
            labels.append(lab.strip())
    seen: set[str] = set()
    out: list[str] = []
    for lab in labels:
        if lab not in seen:
            seen.add(lab)
            out.append(lab)
        if len(out) >= 6:
            break
    return " · ".join(out) if out else ""


def _band_short_label(band: str | None) -> str:
    if not band:
        return "-"
    b = str(band).lower()
    if "below" in b:
        return "Below"
    if "above" in b:
        return "Above"
    if "within" in b:
        return "Within"
    return str(band)


def _sanitize_evidence_cards(cards: list) -> list[dict]:
    out = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        ev = card.get("evidence") or []
        if not isinstance(ev, list):
            ev = []
        out.append(
            {
                "feature_key": card.get("feature_key"),
                "feature_name": card.get("feature_name") or card.get("feature_key") or "-",
                "score": card.get("score"),
                "bucket": card.get("bucket") or "-",
                "label": card.get("label") or "-",
                "evidence": [str(x) for x in ev[:4]],
            }
        )
    return out


def _pen_cards(report: dict) -> list[dict]:
    pen = report.get("pen") or []
    if isinstance(pen, list) and len(pen) >= 1:
        rows = []
        for p in pen:
            if not isinstance(p, dict):
                continue
            rows.append(
                {
                    "name": p.get("name") or "-",
                    "score": p.get("score"),
                    "key": p.get("key"),
                }
            )
        return rows[:3]
    by_key = {}
    for f in report.get("features") or []:
        if not isinstance(f, dict):
            continue
        k = f.get("key")
        if k in ("psychoticism_proxy", "extraversion_proxy", "neuroticism_proxy"):
            by_key[k] = {"name": f.get("name") or k, "score": f.get("score"), "key": k}
    order = ["psychoticism_proxy", "extraversion_proxy", "neuroticism_proxy"]
    return [by_key[k] for k in order if k in by_key]


def _features_for_template(report: dict) -> list[dict]:
    rows = []
    for f in report.get("features") or []:
        if not isinstance(f, dict):
            continue
        conf = f.get("confidence") if isinstance(f.get("confidence"), dict) else {}
        low = f.get("confidence_low")
        high = f.get("confidence_high")
        if low is None:
            low = conf.get("low")
        if high is None:
            high = conf.get("high")
        rows.append(
            {
                "name": f.get("name") or f.get("key") or "-",
                "key": f.get("key") or "-",
                "score": f.get("score"),
                "label": f.get("label"),
                "bucket": f.get("bucket"),
                "interpretation_status": f.get("interpretation_status"),
                "confidence_low": low,
                "confidence_high": high,
                "bar_pct": clamp_score(f.get("score")),
            }
        )
    return rows


def _benchmark_rows(report: dict) -> list[dict]:
    rows = []
    for comp in report.get("benchmark_comparisons") or []:
        if not isinstance(comp, dict):
            continue
        rows.append(
            {
                "metric_name": comp.get("metric_name") or comp.get("feature_key") or "-",
                "score": comp.get("score"),
                "low_threshold": comp.get("low_threshold", 35),
                "high_threshold": comp.get("high_threshold", 65),
                "band": comp.get("band"),
                "band_short": _band_short_label(comp.get("band")),
            }
        )
    return rows


_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)
_env.globals["fmt_score"] = fmt_score
_env.globals["bucket_class"] = bucket_class


def build_report_html(report: dict) -> str:
    interpretation = report.get("interpretation") if isinstance(report.get("interpretation"), dict) else {}
    trait_buckets = interpretation.get("trait_buckets") or []
    if not isinstance(trait_buckets, list):
        trait_buckets = []

    ctx = {
        "title": "Psychometric Insights Report",
        "scenario": report.get("scenario"),
        "started_at": fmt_date(report.get("started_at")),
        "completed_at": fmt_date(report.get("completed_at")),
        "duration": fmt_duration(report.get("duration_ms")),
        "session_id": report.get("session_id") or "-",
        "header_disclaimer": (
            "Experimental reflection only. This is not a clinical, diagnostic, or hiring assessment."
        ),
        "decision_style": interpretation.get("decision_style"),
        "strengths": interpretation.get("strengths"),
        "growth_opportunity": interpretation.get("growth_areas"),
        "setting_specific_summary": interpretation.get("setting_specific_summary"),
        "key_signals_line": _compact_key_signals(trait_buckets),
        "construct_counts": construct_coverage(report),
        "features": _features_for_template(report),
        "evidence_cards": _sanitize_evidence_cards(report.get("evidence_cards") or []),
        "benchmark_rows": _benchmark_rows(report),
        "benchmark_footer": (
            "Internal reference band only. Not a clinical, population, or hiring benchmark."
        ),
        "pen_cards": _pen_cards(report),
        "pen_note": "These are experimental proxy signals, not clinical personality scores.",
        "include_debug": bool(report.get("_pdf_include_debug")),
    }

    tpl = _env.get_template("report_print.html")
    return tpl.render(**ctx)
