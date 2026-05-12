"""Controlled metric simulation graphs.

These helpers produce deterministic, formula-driven figures that illustrate
the scoring system's behaviour. They are intentionally isolated from the live
scoring pipeline so they cannot affect production calculations or DB writes.

The graphs are *controlled scoring simulations*. They are not population
norms, clinical validation, or diagnostic thresholds.
"""

from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FOOTER_NOTE = "Controlled scoring simulation; not population norms."

PROFILE_NAMES: list[str] = [
    "Balanced decisive",
    "High conflict",
    "Time-pressure struggle",
    "Social assertive",
]

METRIC_LABELS: list[str] = [
    "CDI",
    "ADQ",
    "Risk",
    "Social",
    "TPR",
    "Cons",
    "Engage",
    "Psy",
    "Ext",
    "Neu",
]

CONTROLLED_PROFILE_MATRIX: list[list[int]] = [
    [32, 82, 42, 55, 88, 76, 92, 40, 56, 28],
    [78, 54, 48, 52, 63, 42, 74, 50, 54, 75],
    [66, 28, 50, 45, 25, 55, 45, 55, 45, 62],
    [34, 76, 46, 96, 80, 70, 89, 38, 88, 32],
]


def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp ``v`` to the inclusive range [lo, hi]."""

    try:
        x = float(v)
    except (TypeError, ValueError):
        return float(lo)
    if math.isnan(x):
        return float(lo)
    return max(float(lo), min(float(hi), x))


def confidence_margin(n: int, telemetry_penalty: float) -> float:
    """Half-width of the confidence band as a function of evidence count.

    Mirrors the shape of ``confidence_band`` in ``app.confidence`` without
    importing it; this keeps the simulation reproducible even if the live
    scorer changes.
    """

    n_eff = max(int(n or 0), 1)
    raw = 24.0 / math.sqrt(n_eff) + float(telemetry_penalty or 0.0)
    return clamp(raw, 6.0, 30.0)


def shrunk_score(raw_score: float, n: int, prior: float = 0.50, prior_weight: int = 4) -> float:
    """Bayesian-style shrinkage toward a 0.5 prior on a 0..100 scale."""

    n_eff = max(int(n or 0), 0)
    weighted = ((float(raw_score) / 100.0) * n_eff + float(prior) * prior_weight) / (n_eff + prior_weight)
    return clamp(weighted * 100.0, 0.0, 100.0)


def adq_item(option_quality: float, latency_ratio: float, timed_out: bool = False) -> float:
    """ADQ-style item contribution on a 0..100 scale."""

    if timed_out:
        return 0.0
    q = clamp(option_quality, 0.0, 1.0)
    lr = clamp(latency_ratio, 0.0, 1.0)
    value = 100.0 * (0.60 * q + 0.25 * (1.0 - lr) + 0.15 * (1.0 - (1.0 if timed_out else 0.0)))
    return clamp(value, 0.0, 100.0)


def get_controlled_profile_matrix() -> np.ndarray:
    """Return the controlled profile matrix as a 4x10 numpy array."""

    return np.array(CONTROLLED_PROFILE_MATRIX, dtype=float)


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


def _save(fig: plt.Figure, output_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def plot_controlled_profile_heatmap(output_path: str) -> str:
    matrix = get_controlled_profile_matrix()
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    im = ax.imshow(matrix, cmap="viridis", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(METRIC_LABELS)))
    ax.set_xticklabels(METRIC_LABELS, rotation=35, ha="right")
    ax.set_yticks(range(len(PROFILE_NAMES)))
    ax.set_yticklabels(PROFILE_NAMES)
    ax.set_title("Controlled Profile Scores Across User-Report Metrics", pad=14)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            color = "white" if value < 55 else "black"
            ax.text(j, i, f"{int(value)}", ha="center", va="center", color=color, fontsize=9)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Score (0-100)")
    cbar.set_ticks([0, 25, 50, 75, 100])

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def plot_confidence_band_margin(output_path: str) -> str:
    ns = np.arange(1, 41)
    penalties: Sequence[float] = (0.0, 4.0, 8.0)
    colors = ("#1f77b4", "#ff7f0e", "#d62728")

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for penalty, color in zip(penalties, colors):
        margins = [confidence_margin(int(n), penalty) for n in ns]
        ax.plot(ns, margins, marker="o", markersize=3, linewidth=1.8, color=color, label=f"telemetry penalty = {int(penalty)}")

    ax.set_title("Confidence Band Narrows as Evidence Count Increases", pad=10)
    ax.set_xlabel("Evidence count n")
    ax.set_ylabel("Confidence band half-width")
    ax.set_ylim(0, 32)
    ax.set_xlim(0, 41)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", framealpha=0.95)

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def plot_adq_sensitivity(output_path: str) -> str:
    latency = np.linspace(0.1, 1.0, 19)
    qualities = (0.4, 0.7, 1.0)
    colors = ("#7f7f7f", "#2ca02c", "#1f77b4")

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for q, color in zip(qualities, colors):
        values = [adq_item(q, float(lr), timed_out=False) for lr in latency]
        ax.plot(latency, values, marker="o", markersize=3, linewidth=1.8, color=color, label=f"option_quality = {q:.1f}")

    ax.axhline(0, color="#d62728", linestyle="--", linewidth=1.2, label="timeout (timed_out=True)")
    ax.set_title("ADQ Sensitivity to Latency and Choice Quality", pad=10)
    ax.set_xlabel("Latency ratio")
    ax.set_ylabel("ADQ item contribution (0-100)")
    ax.set_ylim(-5, 105)
    ax.set_xlim(0, 1.02)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper right", framealpha=0.95)

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def plot_small_sample_shrinkage(output_path: str) -> str:
    raw = np.linspace(0, 100, 51)
    n_values = (2, 5, 15, 30)
    colors = ("#d62728", "#ff7f0e", "#2ca02c", "#1f77b4")

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.plot(raw, raw, linestyle="--", color="#444444", linewidth=1.2, label="no shrinkage (y = raw)")
    for n, color in zip(n_values, colors):
        values = [shrunk_score(float(r), n) for r in raw]
        ax.plot(raw, values, linewidth=1.8, color=color, label=f"n = {n}")

    ax.set_title("Small-Sample Shrinkage Pulls Scores Toward 50", pad=10)
    ax.set_xlabel("Raw metric score (0-100)")
    ax.set_ylabel("Displayed shrunk score")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper left", framealpha=0.95)

    _apply_common_style(fig)
    plt.tight_layout(rect=(0, 0.03, 1, 1))
    return _save(fig, output_path)


def generate_metric_simulation_graphs(output_dir: str) -> list[str]:
    """Generate the four controlled simulation graphs into ``output_dir``.

    Returns the list of written file paths.
    """

    os.makedirs(output_dir, exist_ok=True)
    paths = [
        plot_controlled_profile_heatmap(os.path.join(output_dir, "G1_controlled_profile_heatmap.png")),
        plot_confidence_band_margin(os.path.join(output_dir, "G2_confidence_band_margin.png")),
        plot_adq_sensitivity(os.path.join(output_dir, "G3_adq_sensitivity.png")),
        plot_small_sample_shrinkage(os.path.join(output_dir, "G4_small_sample_shrinkage.png")),
    ]
    return paths


__all__ = [
    "FOOTER_NOTE",
    "PROFILE_NAMES",
    "METRIC_LABELS",
    "CONTROLLED_PROFILE_MATRIX",
    "clamp",
    "confidence_margin",
    "shrunk_score",
    "adq_item",
    "get_controlled_profile_matrix",
    "plot_controlled_profile_heatmap",
    "plot_confidence_band_margin",
    "plot_adq_sensitivity",
    "plot_small_sample_shrinkage",
    "generate_metric_simulation_graphs",
]
