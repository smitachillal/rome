"""
Load the saved recommender and produce medicine recommendations for a patient.

The joblib bundle (built by ml/pipelines/train_recommender.py) holds the fitted
ML ranker, its feature columns, and the per-drug handbook features. This service
loads it ONCE and reuses it — combining the ML ranking with the handbook safety
filter to return a renally-safe, ranked recommendation list.
"""
from __future__ import annotations
import os
from functools import lru_cache
import numpy as np
import pandas as pd
import joblib

from app.core.renal_calc import ckd_stage

BUNDLE_PATH = os.getenv("RECOMMENDER_PATH", "../models/model_gb.joblib")

# hard renal avoid thresholds (eGFR) — same backstop as handbook_safety
AVOID_BELOW = {
    "metformin": 30, "nitrofurantoin": 45, "dabigatran": 30, "spironolactone": 30,
    "apixaban": 15, "rivaroxaban": 15, "enoxaparin": 15, "sitagliptin": 15,
    "ramipril": 15, "lisinopril": 15, "enalapril": 15,
}


@lru_cache(maxsize=1)
def _bundle():
    if not os.path.exists(BUNDLE_PATH):
        return None
    return joblib.load(BUNDLE_PATH)


def recommender_available() -> bool:
    return _bundle() is not None


def _handbook_status(drug: str, egfr: float, dose_rules: dict) -> tuple[str, str]:
    """Lightweight safety verdict at the patient's eGFR."""
    avoid = AVOID_BELOW.get(drug)
    if avoid is not None and egfr < avoid:
        return "avoid", f"Avoid: eGFR {egfr:g} below {avoid} mL/min"
    if egfr >= 50:
        return "normal", "Dose as in normal renal function"
    # dose_rules maps band -> action text if available
    band = "20-50" if egfr >= 20 else ("10-20" if egfr >= 10 else "under10")
    action = (dose_rules or {}).get(band, "")
    if "avoid" in action.lower():
        return "avoid", action
    if action:
        return "caution", action
    return "caution", "Reduce dose / monitor — see handbook"


def recommend(patient, top_k: int = 8) -> dict:
    """patient: dict with age, sex, weight_kg, egfr, crcl, aki_stage, ckd_stage,
    diagnoses (list of categories), n_existing_drugs. Returns recommendation dict."""
    b = _bundle()
    if b is None:
        return {"available": False, "reason": "No trained recommender. "
                "Run ml/pipelines/train_recommender.py.", "suggestions": []}

    ranker, cols, dfeat = b["ranker"], b["feature_cols"], b["drug_features"]
    CATALOGUE, DIAGNOSES = b["catalogue"], b["diagnoses"]

    rows = []
    for drug in CATALOGUE:
        rows.append({
            "age": patient["age"], "sex": patient["sex"], "weight_kg": patient["weight_kg"],
            "egfr": patient["egfr"], "crcl": patient["crcl"],
            "aki_stage": patient["aki_stage"], "ckd_stage": patient["ckd_stage"],
            "n_existing_drugs": patient.get("n_existing_drugs", 0),
            **{f"dx_{dx}": int(dx in patient.get("diagnoses", [])) for dx in DIAGNOSES},
            "drug_pct_excreted": dfeat[drug]["drug_pct_excreted"],
            "drug_half_life": dfeat[drug]["drug_half_life"],
            "drug_protein_binding": dfeat[drug]["drug_protein_binding"],
            "drug_class": dfeat[drug]["drug_class"],
            "drug_indication": dfeat[drug]["drug_indication"],
        })
    feat = pd.DataFrame(rows, index=list(CATALOGUE))
    scores = ranker.predict_proba(feat[cols])[:, 1]

    out = []
    for drug, score in zip(CATALOGUE, scores):
        status, dose = _handbook_status(drug, patient["egfr"],
                                        dfeat[drug].get("dose_rules"))
        out.append({
            "drug": drug, "ml_score": round(float(score), 3),
            "indication": dfeat[drug]["drug_indication"],
            "safety": status, "dose_guidance": dose,
            "reference": "Renal Drug Handbook (5th ed.)",
        })
    out.sort(key=lambda r: r["ml_score"], reverse=True)
    safe = [r for r in out if r["safety"] != "avoid"][:top_k]
    removed = [r for r in out if r["safety"] == "avoid"]

    return {"available": True, "best_model": b.get("best_model"),
            "suggestions": safe, "removed": removed}
