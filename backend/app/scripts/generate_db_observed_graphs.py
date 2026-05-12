"""CLI: produce DB-observed evaluation graphs from existing data.

This script reads only data that the application already persists:
    - reports.report_json
    - derived_features (feature_key/feature_score/confidence_low/confidence_high/evidence_count)
    - choices.telemetry_json / traits_json / scene_metadata / time_limit_sec

No new tables are created. No PII is included in the graphs. Graphs are
skipped (with a clear message) when there is not enough stored data.

Usage:
    python -m app.scripts.generate_db_observed_graphs
    python -m app.scripts.generate_db_observed_graphs --output-dir backend/generated_graphs
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.evaluation_graphs import FOOTER_NOTE, clamp
from app.models import Choice, DerivedFeature, Report, Session as SessionRow


PROFILE_GROUPS = [
    "Time-pressure struggle",
    "High conflict",
    "Social assertive",
    "Balanced decisive",
    "Other",
]


def _default_output_dir() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    return str(backend_root / "generated_graphs")


def _apply_common_style(fig: plt.Figure) -> None:
    fig.patch.set_facecolor("white")
    fig.text(
        0.5,
        0.012,
        FOOTER_NOTE,
        ha="center",
        va="bottom",
        fontsize=8,
        color="#666666",
    )


def _save(fig: plt.Figure, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _classify_profile(features_by_key: dict[str, float]) -> str:
    """Bucket a completed session by its derived-feature scores.

    Priority order is preserved so a single session lands in only one bucket.
    """

    cdi = features_by_key.get("cdi")
    adq = features_by_key.get("adq")
    tpr = features_by_key.get("time_pressure_resilience")
    neu = features_by_key.get("neuroticism_proxy")
    social = features_by_key.get("social_influence_sensitivity")
    extra = features_by_key.get("extraversion_proxy")

    if (adq is not None and adq < 45) or (tpr is not None and tpr < 45):
        return "Time-pressure struggle"
    if (cdi is not None and cdi >= 65) or (neu is not None and neu >= 65):
        return "High conflict"
    if (social is not None and social >= 65) or (extra is not None and extra >= 65):
        return "Social assertive"
    if (
        cdi is not None
        and adq is not None
        and tpr is not None
        and cdi < 45
        and adq >= 65
        and tpr >= 65
    ):
        return "Balanced decisive"
    return "Other"


def _collect_completed_sessions(db) -> list[dict]:
    rows = db.execute(
        select(SessionRow).where(SessionRow.completed_at.isnot(None))
    ).scalars().all()
    return [{"id": r.id} for r in rows]


def _collect_features_by_session(db, session_ids: Iterable[str]) -> dict[str, dict[str, dict]]:
    ids = list(session_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(DerivedFeature).where(DerivedFeature.session_id.in_(ids))
    ).scalars().all()
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        out[r.session_id][r.feature_key] = {
            "score": float(r.feature_score or 0.0),
            "confidence_low": float(r.confidence_low or 0.0),
            "confidence_high": float(r.confidence_high or 0.0),
            "evidence_count": int(r.evidence_count or 0),
        }
    return out


def _generate_db1_feature_heatmap(db, output_path: str) -> str | None:
    sessions = _collect_completed_sessions(db)
    if len(sessions) < 2:
        print("Skipping DB1: not enough completed sessions with derived features.")
        return None
    features_by_session = _collect_features_by_session(db, [s["id"] for s in sessions])
    if not features_by_session:
        print("Skipping DB1: not enough completed sessions with derived features.")
        return None

    group_scores: dict[str, dict[str, list[float]]] = {g: defaultdict(list) for g in PROFILE_GROUPS}
    group_counts: dict[str, int] = {g: 0 for g in PROFILE_GROUPS}

    feature_keys: list[str] = []
    feature_key_set: set[str] = set()

    for session_id, features in features_by_session.items():
        score_map = {k: v["score"] for k, v in features.items()}
        group = _classify_profile(score_map)
        group_counts[group] += 1
        for key, score in score_map.items():
            group_scores[group][key].append(score)
            if key not in feature_key_set:
                feature_keys.append(key)
                feature_key_set.add(key)

    active_groups = [g for g in PROFILE_GROUPS if group_counts[g] > 0]
    if not active_groups or not feature_keys:
        print("Skipping DB1: not enough completed sessions with derived features.")
        return None

    matrix = np.full((len(active_groups), len(feature_keys)), np.nan, dtype=float)
    for i, group in enumerate(active_groups):
        for j, key in enumerate(feature_keys):
            values = group_scores[group].get(key) or []
            if values:
                matrix[i, j] = float(np.mean(values))

    fig, ax = plt.subplots(figsize=(max(9.0, 0.8 * len(feature_keys) + 4), 1.0 * len(active_groups) + 2.5))
    masked = np.ma.masked_invalid(matrix)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad(color="#e0e0e0")
    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(feature_keys)))
    ax.set_xticklabels(feature_keys, rotation=35, ha="right")
    ax.set_yticks(range(len(active_groups)))
    ax.set_yticklabels([f"{g} (n={group_counts[g]})" for g in active_groups])
    ax.set_title("Observed Average Feature Scores by Profile Group", pad=12)

    for i in range(masked.shape[0]):
        for j in range(masked.shape[1]):
            value = matrix[i, j]
            if np.isnan(value):
                ax.text(j, i, "—", ha="center", va="center", color="#777777", fontsize=9)
            else:
                color = "white" if value < 55 else "black"
                ax.text(j, i, f"{int(round(value))}", ha="center", va="center", color=color, fontsize=9)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Average feature_score (0-100)")
    cbar.set_ticks([0, 25, 50, 75, 100])

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def _generate_db2_confidence_vs_evidence(db, output_path: str) -> str | None:
    rows = db.execute(select(DerivedFeature)).scalars().all()
    points: list[tuple[int, float, str]] = []
    for r in rows:
        try:
            low = float(r.confidence_low)
            high = float(r.confidence_high)
            evidence = int(r.evidence_count or 0)
        except (TypeError, ValueError):
            continue
        if high <= 0 and low <= 0:
            continue
        half_width = max(0.0, (high - low) / 2.0)
        points.append((evidence, half_width, str(r.feature_key or "feature")))

    if len(points) < 3:
        print("Skipping DB2: not enough derived features with confidence values.")
        return None

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    keys = sorted({p[2] for p in points})
    cmap = plt.get_cmap("tab10")
    color_for_key = {k: cmap(i % 10) for i, k in enumerate(keys)}

    for key in keys:
        xs = [p[0] for p in points if p[2] == key]
        ys = [p[1] for p in points if p[2] == key]
        ax.scatter(xs, ys, color=color_for_key[key], alpha=0.75, s=28, edgecolors="white", linewidths=0.5, label=key)

    ax.set_title("Observed Confidence Half-Width vs Evidence Count", pad=10)
    ax.set_xlabel("Evidence count")
    ax.set_ylabel("Confidence band half-width")
    ax.grid(True, linestyle="--", alpha=0.35)
    if len(keys) <= 8:
        ax.legend(loc="upper right", framealpha=0.95, fontsize=8)

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def _option_quality(choice: Choice) -> float | None:
    traits = choice.traits_json or {}
    if not isinstance(traits, dict):
        return None
    risk = traits.get("risk")
    empathy = traits.get("empathy")
    decisiveness = traits.get("decisiveness")
    emotional = traits.get("emotional_regulation")
    parts: list[float] = []
    if isinstance(risk, (int, float)):
        parts.append(1.0 - float(risk))
    if isinstance(empathy, (int, float)):
        parts.append(float(empathy))
    if isinstance(decisiveness, (int, float)):
        parts.append(float(decisiveness))
    if isinstance(emotional, (int, float)):
        parts.append(float(emotional))
    if not parts:
        return None
    return clamp(sum(parts) / len(parts), 0.0, 1.0)


def _latency_ratio(choice: Choice) -> float | None:
    telemetry = choice.telemetry_json or {}
    if not isinstance(telemetry, dict):
        return None
    if isinstance(telemetry.get("latency_ratio"), (int, float)):
        return clamp(float(telemetry["latency_ratio"]), 0.0, 1.0)
    latency_ms = telemetry.get("latency_ms")
    time_limit_sec = choice.time_limit_sec or 45
    if isinstance(latency_ms, (int, float)) and time_limit_sec:
        return clamp(float(latency_ms) / (float(time_limit_sec) * 1000.0), 0.0, 1.0)
    return None


def _generate_db3_adq_latency_quality(db, output_path: str) -> str | None:
    rows = db.execute(select(Choice)).scalars().all()
    xs: list[float] = []
    ys: list[float] = []
    colors: list[str] = []
    for r in rows:
        lr = _latency_ratio(r)
        q = _option_quality(r)
        if lr is None or q is None:
            continue
        timed_out = bool((r.telemetry_json or {}).get("timed_out"))
        xs.append(lr)
        ys.append(q * 100.0)
        colors.append("#d62728" if timed_out else "#1f77b4")

    if len(xs) < 5:
        print("Skipping DB3: not enough choices with latency/traits to plot.")
        return None

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.scatter(xs, ys, c=colors, s=28, alpha=0.75, edgecolors="white", linewidths=0.5)
    ax.set_title("Observed Choice Quality vs Latency Ratio", pad=10)
    ax.set_xlabel("Latency ratio")
    ax.set_ylabel("Choice quality proxy (0-100)")
    ax.set_xlim(-0.02, 1.05)
    ax.set_ylim(-2, 102)
    ax.grid(True, linestyle="--", alpha=0.35)
    legend_handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", color="#1f77b4", label="not timed out", markersize=7),
        plt.Line2D([0], [0], marker="o", linestyle="", color="#d62728", label="timed out", markersize=7),
    ]
    ax.legend(handles=legend_handles, loc="upper right", framealpha=0.95)

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def _generate_db4_score_distribution(db, output_path: str) -> str | None:
    rows = db.execute(select(DerivedFeature)).scalars().all()
    if len(rows) < 10:
        print("Skipping DB4: fewer than 10 derived feature rows.")
        return None

    by_key: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        try:
            by_key[str(r.feature_key or "feature")].append(float(r.feature_score or 0.0))
        except (TypeError, ValueError):
            continue

    keys = [k for k, vs in by_key.items() if len(vs) >= 1]
    if not keys:
        print("Skipping DB4: no usable feature_score values.")
        return None

    keys.sort()
    data = [by_key[k] for k in keys]

    fig, ax = plt.subplots(figsize=(max(8.5, 0.6 * len(keys) + 4), 5.0))
    try:
        bp = ax.boxplot(
            data,
            tick_labels=keys,
            patch_artist=True,
            showfliers=True,
            medianprops=dict(color="#222222", linewidth=1.4),
        )
    except TypeError:
        bp = ax.boxplot(
            data,
            labels=keys,
            patch_artist=True,
            showfliers=True,
            medianprops=dict(color="#222222", linewidth=1.4),
        )
    cmap = plt.get_cmap("tab20")
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(cmap(i % 20))
        patch.set_alpha(0.55)
        patch.set_edgecolor("#444444")

    ax.set_title("Observed Feature Score Distribution", pad=10)
    ax.set_xlabel("Feature key")
    ax.set_ylabel("feature_score (0-100)")
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def generate_db_observed_graphs(output_dir: str) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []

    try:
        init_db()
    except Exception as exc:
        print(f"Database not available: {exc}")
        return written

    with SessionLocal() as db:
        for name, fn in (
            ("DB1_observed_feature_heatmap.png", _generate_db1_feature_heatmap),
            ("DB2_observed_confidence_vs_evidence.png", _generate_db2_confidence_vs_evidence),
            ("DB3_observed_adq_latency_quality.png", _generate_db3_adq_latency_quality),
            ("DB4_observed_score_distribution.png", _generate_db4_score_distribution),
        ):
            target = os.path.join(output_dir, name)
            try:
                result = fn(db, target)
            except Exception as exc:
                print(f"Skipping {name}: error while generating ({exc}).")
                continue
            if result:
                written.append(result)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate DB-observed evaluation graphs.")
    parser.add_argument(
        "--output-dir",
        default=_default_output_dir(),
        help="Directory to write generated PNG files (default: backend/generated_graphs).",
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=["png"],
        help="Output format (currently only png is supported).",
    )
    parser.add_argument(
        "--show",
        default="false",
        choices=["true", "false"],
        help="Interactive display is disabled; flag accepted for compatibility.",
    )
    args = parser.parse_args(argv)

    output_dir = os.path.abspath(args.output_dir)
    paths = generate_db_observed_graphs(output_dir)

    print(f"DB-observed graphs directory: {output_dir}")
    if not paths:
        print("No DB graphs were written.")
    else:
        for p in paths:
            print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
