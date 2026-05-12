import os

import pytest

from app.evaluation_graphs import (
    adq_item,
    confidence_margin,
    generate_metric_simulation_graphs,
    get_controlled_profile_matrix,
    shrunk_score,
)


def test_confidence_margin_low_n_is_clamped_high():
    margin = confidence_margin(1, 0)
    assert margin <= 30
    assert margin >= 6


def test_confidence_margin_high_n_is_clamped_low():
    margin = confidence_margin(40, 0)
    assert margin >= 6
    assert margin <= 30


def test_confidence_margin_penalty_increases_band():
    assert confidence_margin(20, 8) >= confidence_margin(20, 0)


def test_adq_item_timed_out_is_zero():
    assert adq_item(1.0, 0.1, timed_out=True) == 0.0


def test_adq_item_perfect_quality_low_latency_is_high():
    assert adq_item(1.0, 0.1, timed_out=False) > 80


def test_shrunk_score_pulls_high_value_down():
    assert shrunk_score(100, 2) < 100


def test_shrunk_score_pulls_low_value_up():
    assert shrunk_score(0, 2) > 0


def test_shrunk_score_large_n_close_to_raw():
    assert abs(shrunk_score(80, 200) - 80) < 1.5


def test_controlled_profile_matrix_shape():
    matrix = get_controlled_profile_matrix()
    assert matrix.shape == (4, 10)


def test_generate_metric_simulation_graphs_writes_four_files(tmp_path):
    paths = generate_metric_simulation_graphs(str(tmp_path))
    assert len(paths) == 4
    for p in paths:
        assert os.path.exists(p)
        assert os.path.getsize(p) > 0
    names = sorted(os.path.basename(p) for p in paths)
    assert names == [
        "G1_controlled_profile_heatmap.png",
        "G2_confidence_band_margin.png",
        "G3_adq_sensitivity.png",
        "G4_small_sample_shrinkage.png",
    ]
