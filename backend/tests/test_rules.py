"""Unit tests for the deterministic rule layer."""
from app.core.rules import evaluate_drug


def test_metformin_review_band():
    f = evaluate_drug("metformin", egfr=41, crcl=None)
    assert f["severity"] == "review"
    assert f["metric"] == "eGFR"


def test_metformin_urgent_band():
    f = evaluate_drug("metformin", egfr=25, crcl=None)
    assert f["severity"] == "urgent"


def test_metformin_within_range():
    f = evaluate_drug("metformin", egfr=70, crcl=None)
    assert f["severity"] == "none"


def test_apixaban_uses_crcl_not_egfr():
    # eGFR ok but CrCl low -> must flag on CrCl
    f = evaluate_drug("apixaban", egfr=55, crcl=20)
    assert f["metric"] == "CrCl"
    assert f["severity"] == "review"


def test_level_guided_manual_when_impaired():
    f = evaluate_drug("digoxin", egfr=30, crcl=None)
    assert f["severity"] == "manual"


def test_unknown_drug_returns_none():
    assert evaluate_drug("paracetamol", egfr=30, crcl=None) is None
