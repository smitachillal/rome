"""
Serve the saved potassium breach-risk model.

Loads ml/potassium.joblib ONCE (cached) and predicts, from a patient's own
history, the probability their NEXT potassium reading breaches an action
threshold (>= 5.5 or < 3.5 mmol/L). This is the ML half of Proposal 2; the
drug-level suggestions in potassium.py (suggest_medicines, if you have it, or
rule_assessment) are the separate rule-layer half.
"""
from __future__ import annotations
import os
from functools import lru_cache
import numpy as np
import pandas as pd
import joblib

from app.services.potassium import K_DRUGS, RAISING, LOWERING

BUNDLE_PATH = os.getenv("POTASSIUM_MODEL_PATH", "ml/potassium.joblib")
CK_ORDER = {"G1": 1, "G2": 2, "G3a": 3, "G3b": 4, "G4": 5, "G5": 5}


@lru_cache(maxsize=1)
def _bundle():
    if not os.path.exists(BUNDLE_PATH):
        return None
    return joblib.load(BUNDLE_PATH)


def predictor_available() -> bool:
    return _bundle() is not None


def predict_for_patient(patient) -> dict:
    """patient: a Patient ORM object (labs, drugs relationships)."""
    b = _bundle()
    if b is None:
        return {"available": False,
                "reason": "No trained potassium model. Run potassium_model.py --save-model."}

    k_labs = sorted([l for l in patient.labs if l.potassium_mmol_l is not None],
                    key=lambda l: l.measured_on)
    if len(k_labs) < 3:
        return {"available": False,
                "reason": f"Need >= 3 potassium readings to predict; have {len(k_labs)}."}

    hist = [l.potassium_mmol_l for l in k_labs]
    latest_egfr = next((l.egfr for l in reversed(k_labs) if l.egfr is not None), None)
    latest_creat = next((l.creatinine_mgdl for l in reversed(k_labs) if l.creatinine_mgdl is not None), None)

    meds = [str(d.ingredient).lower() for d in patient.drugs]
    r = [d for d in meds if d in RAISING]
    l = [d for d in meds if d in LOWERING]

    x = np.arange(len(hist))
    row = {
        "age": patient.age,
        "egfr": latest_egfr, "creatinine": latest_creat,
        "ckd_stage_ord": CK_ORDER.get(patient.ckd_stage or "", 3),
        "k_last": hist[-1], "k_mean": float(np.mean(hist)),
        "k_slope": float(np.polyfit(x, hist, 1)[0]) if len(hist) > 1 else 0.0,
        "k_max": max(hist), "k_min": min(hist),
        "n_raising": len(r), "n_lowering": len(l),
        "raising_burden": sum(K_DRUGS[d][1] for d in r),
        "lowering_burden": sum(K_DRUGS[d][1] for d in l),
        "net_k_burden": sum(K_DRUGS[d][1] for d in r) - sum(K_DRUGS[d][1] for d in l),
    }
    feat = pd.DataFrame([row])[b["features"]]
    proba = float(b["model"].predict_proba(feat)[0, 1])

    direction = "hyperkalaemia" if row["net_k_burden"] >= 0 else "hypokalaemia"
    driver = None
    agents = sorted(r, key=lambda d: -K_DRUGS[d][1]) if direction == "hyperkalaemia" \
        else sorted(l, key=lambda d: -K_DRUGS[d][1])
    if agents:
        driver = {"drug": agents[0], "class": K_DRUGS[agents[0]][2]}

    return {
        "available": True,
        "model": b["model_name"],
        "model_metrics": b["metrics"],
        "breach_probability": round(proba, 3),
        "risk_band": ("high" if proba >= 0.6 else "moderate" if proba >= 0.3 else "low"),
        "likely_direction": direction if proba >= 0.3 else None,
        "likely_driver": driver,
        "inputs": row,
    }
