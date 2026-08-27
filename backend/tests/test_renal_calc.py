"""Unit tests for the renal parameter calculations."""
from datetime import date, timedelta

import pytest

from app.core.renal_calc import (
    egfr_ckd_epi_2021, cockcroft_gault, umol_to_mgdl, ideal_body_weight,
    aki_stage_for_point, aki_stages_for_series, ckd_stage, ckd_confirmed,
    egfr_reliable,
)


# ---------------- eGFR ----------------
def test_egfr_normal_creatinine_is_healthy_range():
    # 60y male, Scr 0.9 mg/dL -> around 90-100
    v = egfr_ckd_epi_2021(0.9, 60, "M")
    assert 85 < v < 105


def test_egfr_falls_as_creatinine_rises():
    high = egfr_ckd_epi_2021(0.8, 70, "F")
    low = egfr_ckd_epi_2021(3.0, 70, "F")
    assert low < high


def test_egfr_female_adjustment_applied():
    m = egfr_ckd_epi_2021(1.0, 65, "M")
    f = egfr_ckd_epi_2021(1.0, 65, "F")
    assert f != m          # sex-specific kappa/alpha change the result


def test_egfr_rejects_bad_input():
    assert egfr_ckd_epi_2021(0, 60, "M") is None
    assert egfr_ckd_epi_2021(-1, 60, "M") is None


# ---------------- CrCl ----------------
def test_cockcroft_gault_matches_hand_calculation():
    # (140-70) x 70kg x 1.0 / (72 x 1.0) = 68.06
    assert cockcroft_gault(1.0, 70, "M", 70) == pytest.approx(68.1, abs=0.1)


def test_cockcroft_gault_female_factor():
    m = cockcroft_gault(1.0, 70, "M", 70)
    f = cockcroft_gault(1.0, 70, "F", 70)
    assert f == pytest.approx(m * 0.85, abs=0.1)


def test_crcl_none_without_weight():
    assert cockcroft_gault(1.0, 70, "M", None) is None


def test_crcl_differs_from_egfr_by_body_size():
    """Same creatinine, different weight -> same eGFR but different CrCl.
    This is the whole reason both metrics are stored."""
    eg = egfr_ckd_epi_2021(1.2, 70, "M")
    light = cockcroft_gault(1.2, 70, "M", 55)
    heavy = cockcroft_gault(1.2, 70, "M", 95)
    assert eg is not None
    assert heavy > light            # eGFR identical, CrCl is not


# ---------------- units ----------------
def test_umol_conversion():
    assert umol_to_mgdl(88.4) == pytest.approx(1.0, abs=0.001)


def test_ideal_body_weight_devine():
    # 5'10" male = 70in -> 50 + 2.3*10 = 73
    assert ideal_body_weight(177.8, "M") == pytest.approx(73.0, abs=0.5)


# ---------------- AKI (KDIGO, creatinine route) ----------------
def _series(vals, start=date(2025, 1, 1), step=1):
    return [(start + timedelta(days=i * step), v) for i, v in enumerate(vals)]


def test_aki_absolute_rise_within_48h_is_stage1():
    hist = [(date(2025, 1, 1), 1.0)]
    assert aki_stage_for_point(date(2025, 1, 2), 1.35, hist) == 1


def test_aki_small_rise_is_not_aki():
    hist = [(date(2025, 1, 1), 1.0)]
    assert aki_stage_for_point(date(2025, 1, 2), 1.15, hist) == 0


def test_aki_ratio_1_5_is_stage1():
    hist = [(date(2025, 1, 1), 1.0)]
    assert aki_stage_for_point(date(2025, 1, 5), 1.6, hist) == 1


def test_aki_ratio_2_is_stage2():
    hist = [(date(2025, 1, 1), 1.0)]
    assert aki_stage_for_point(date(2025, 1, 5), 2.2, hist) == 2


def test_aki_ratio_3_is_stage3():
    hist = [(date(2025, 1, 1), 1.0)]
    assert aki_stage_for_point(date(2025, 1, 5), 3.4, hist) == 3


def test_aki_absolute_4_mgdl_is_stage3_even_without_history():
    assert aki_stage_for_point(date(2025, 1, 1), 4.5, []) == 3


def test_aki_stable_series_never_flags():
    s = _series([1.0, 1.02, 0.98, 1.01], step=30)
    assert aki_stages_for_series(s) == [0, 0, 0, 0]


def test_aki_spike_is_detected_in_series():
    s = _series([1.0, 1.0, 3.0, 1.2], step=1)
    stages = aki_stages_for_series(s)
    assert stages[2] == 3          # the spike
    assert stages[0] == 0


# ---------------- CKD ----------------
@pytest.mark.parametrize("egfr,expected", [
    (120, "G1"), (95, "G1"), (75, "G2"), (60, "G2"),
    (50, "G3a"), (35, "G3b"), (20, "G4"), (10, "G5"),
])
def test_ckd_stage_bands(egfr, expected):
    assert ckd_stage(egfr) == expected


def test_ckd_stage_none_for_missing():
    assert ckd_stage(None) is None


def test_ckd_chronicity_requires_90_days():
    short = [(date(2025, 1, 1), 50), (date(2025, 2, 1), 48)]     # 31 days
    long = [(date(2025, 1, 1), 50), (date(2025, 6, 1), 48)]      # 151 days
    assert ckd_confirmed(short) is False
    assert ckd_confirmed(long) is True


def test_ckd_not_confirmed_when_egfr_normal():
    ok = [(date(2025, 1, 1), 95), (date(2025, 6, 1), 92)]
    assert ckd_confirmed(ok) is False


# ---------------- interaction ----------------
def test_egfr_unreliable_during_aki():
    assert egfr_reliable(0) is True
    assert egfr_reliable(2) is False
