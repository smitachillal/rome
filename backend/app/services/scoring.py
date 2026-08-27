"""Assemble rule flags + ML risk + explanation into a patient advisory."""
from __future__ import annotations
import numpy as np
from app.core.rules import evaluate_drug
from app.ml.model import predict_risk, explain


def renal_labs(labs):
    """Lab rows that actually carry an eGFR.

    Since potassium was added, a lab row may be a potassium-only draw (no
    creatinine that day), so egfr is NULL. Every renal calculation must filter
    those out first, or it will fail on None.
    """
    return sorted([l for l in labs if l.egfr is not None],
                  key=lambda l: l.measured_on)


def _slope_per_year(labs) -> float:
    labs = renal_labs(labs)
    if len(labs) < 2:
        return 0.0
    t0 = labs[0].measured_on
    yrs = np.array([(l.measured_on - t0).days / 365.25 for l in labs])
    eg = np.array([float(l.egfr) for l in labs])
    if yrs.max() == 0:
        return 0.0
    return float(np.polyfit(yrs, eg, 1)[0])


def build_features(patient) -> dict:
    labs = renal_labs(patient.labs)
    egfrs = [float(l.egfr) for l in labs]
    return {
        "window_last_egfr": egfrs[-1] if egfrs else None,
        "egfr_slope_per_year": _slope_per_year(patient.labs),
        "window_min_egfr": min(egfrs) if egfrs else None,
        "n_renal_drugs": len(patient.drugs),
        "age": patient.age,
        "female": 1 if patient.sex == "F" else 0,
    }


def summarise(patient) -> dict:
    feat = build_features(patient)
    labs = renal_labs(patient.labs)
    if not labs:
        # patient has potassium readings but no eGFR yet -- return a safe summary
        return {"patient_id": patient.id, "name": patient.name, "age": patient.age,
                "sex": patient.sex, "latest_egfr": None, "egfr_slope_per_year": 0.0,
                "n_renal_drugs": len(patient.drugs), "risk_score": 0.0,
                "top_drug": None, "breach": False}
    latest = labs[-1]
    flags = [f for f in (evaluate_drug(d.ingredient, latest.egfr, latest.crcl)
                         for d in patient.drugs) if f]
    breaching = [f for f in flags if f["severity"] in ("review", "urgent")]
    top = max(breaching, key=lambda f: 0 if f["cutoff"] is None
              else f["cutoff"] - (f["value_used"] or 0), default=None)
    risk = predict_risk(feat)
    return {
        "patient_id": patient.id, "name": patient.name, "age": patient.age,
        "sex": patient.sex, "latest_egfr": latest.egfr,  "weight_kg": patient.weight_kg  or 0.0 , 
        "ckd_confirmed": patient.ckd_confirmed, "ckd_stage": patient.ckd_stage, 
        "egfr_slope_per_year": round(feat["egfr_slope_per_year"], 2),
        "n_renal_drugs": len(patient.drugs), "risk_score": round(risk, 3),
        "top_drug": top["ingredient"] if top else (flags[0]["ingredient"] if flags else None),
        "breach": bool(breaching),
    }


def detail(patient) -> dict:
    base = summarise(patient)
    feat = build_features(patient)
    labs = renal_labs(patient.labs)
    if not labs:
        return {**base, "trajectory": [], "drug_flags": [], "explanation": [],
                "advisory": "No eGFR readings for this patient."}
    latest = labs[-1]
    flags = [f for f in (evaluate_drug(d.ingredient, latest.egfr, latest.crcl)
                         for d in patient.drugs) if f]
    exp = explain(feat)[:5]
    urgent = [f for f in flags if f["severity"] == "urgent"]
    review = [f for f in flags if f["severity"] == "review"]
    if urgent:
        advisory = (f"Urgent: {urgent[0]['ingredient']} — {urgent[0]['action']} "
                    f"({urgent[0]['metric']} {urgent[0]['value_used']}).")
    elif review:
        advisory = (f"Review: {review[0]['ingredient']} — {review[0]['action']} "
                    f"({review[0]['metric']} {review[0]['value_used']}).")
    else:
        advisory = "No threshold breach at latest reading; monitor trajectory."
    return {
        **base,
        "trajectory": [{"measured_on": l.measured_on, "egfr": l.egfr, "crcl": l.crcl}
                       for l in labs],
        "drug_flags": flags,
        "explanation": exp,
        "advisory": advisory,
    }
