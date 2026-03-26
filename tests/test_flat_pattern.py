"""Flat-pattern math used for planner width."""
import math

from src.flat_pattern import (
    bend_allowance_mm,
    developed_profile_girth_mm,
    effective_profile_segments,
    profile_bend_count,
)


def test_profile_bend_count():
    assert profile_bend_count(0) == 0
    assert profile_bend_count(1) == 0
    assert profile_bend_count(2) == 1
    assert profile_bend_count(5) == 4


def test_bend_allowance_90_deg():
    # θ=90°, R_inner=3, T=2, K=0.4 → r_n = 3 + 0.8 = 3.8, BA = (π/2)*3.8
    ba = bend_allowance_mm(90, 2.0, 3.0, 0.4)
    expected = (math.pi / 2) * 3.8
    assert abs(ba - expected) < 1e-6


def test_effective_profile_is_only_written_dimensions():
    p = {"profile_dimensions": [30, 1040, 270, 25], "bend_offset_mm": 999}
    assert effective_profile_segments(p) == [30, 1040, 270, 25]


def test_developed_mold_adds_bend_allowance():
    panel = {"profile_dimensions": [30, 1040, 270, 30]}
    header = {
        "thickness_mm": 2,
        "k_factor": 0.4,
        "default_bend_radius_mm": None,
        "bend_allowance_angle_deg": 90,
        "flat_pattern_dimension_basis": "mold",
    }
    g = developed_profile_girth_mm(panel, header)
    assert g is not None
    segs = 30 + 1040 + 270 + 30
    ba = bend_allowance_mm(90, 2.0, max(2 * 1.5, 1.0), 0.4)
    assert abs(g - (segs + 3 * ba)) < 0.01  # 4 segments → 3 bends


def test_developed_legacy_is_horizontal_only():
    panel = {"profile_dimensions": [30, 1040, 270]}
    header = {"flat_pattern_dimension_basis": "legacy"}
    g = developed_profile_girth_mm(panel, header)
    assert g == 30 + 270
