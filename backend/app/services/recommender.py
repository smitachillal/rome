# recommend.py — inference wrapper used by the API
from __future__ import annotations
import os, functools
import pandas as pd
import joblib




from  .prescribing_model import CATALOGUE, DIAGNOSES, drug_features
from .handbook_safety import HandbookSafety



# Override in deployment; prefer ABSOLUTE paths (see note below)
MODEL_PATH = os.getenv("MODEL_PATH", "ml/model_gb.joblib")
HANDBOOK   = os.getenv("HANDBOOK_PATH",
                       "ml/renal_drug_handbook_decision_tree_dataset.csv")


@functools.lru_cache(maxsize=1)
def _artifacts():
    """Load model + handbook once, on first request, then cache."""


    _HERE = os.path.dirname(os.path.abspath(__file__))          # ...\backend\app\services
    _BACKEND = os.path.abspath(os.path.join(_HERE, "..", ".."))  # ...\backend

    MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(_BACKEND, "ml", "model_gb.joblib"))

    print(" os.path.exists(MODEL_PATH) " , os.path.exists(MODEL_PATH) , " path is ", MODEL_PATH )
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"model not found at {MODEL_PATH} (cwd={os.getcwd()})")

    model  = joblib.load(MODEL_PATH)
    print(" model loaded")
    cols   = list(model.feature_names_in_)   # exact column order used at fit time
    dfeat  = drug_features(HANDBOOK)
    print(" model HANDBOOK")
    safety = HandbookSafety(HANDBOOK)
    return model, cols, dfeat, safety


def _feature_frame(patient, dfeat):
    """One row per candidate drug — identical layout to training/suggest()."""
    rows = []
    for drug in CATALOGUE:
        rows.append({
            "age": patient["age"], "sex": patient["sex"],
            "weight_kg": patient["weight_kg"], "egfr": patient["egfr"],
            "crcl": patient["crcl"], "aki_stage": patient["aki_stage"],
            "ckd_stage": patient["ckd_stage"],
            "n_existing_drugs": patient["n_existing_drugs"],
            **{f"dx_{dx}": int(dx in patient["diagnoses"]) for dx in DIAGNOSES},
            "drug_pct_excreted":    dfeat[drug]["drug_pct_excreted"],
            "drug_half_life":       dfeat[drug]["drug_half_life"],
            "drug_protein_binding": dfeat[drug]["drug_protein_binding"],
            "drug_class":           dfeat[drug]["drug_class"],
            "drug_indication":      dfeat[drug]["drug_indication"],
        })
    return pd.DataFrame(rows, index=list(CATALOGUE))


def recommend(patient: dict, top_k: int = 8) -> dict:
    """
    Score every catalogue drug for this patient, screen through the renal
    safety handbook, and return safe ranked suggestions + what was removed.
    `patient` is the dict built in the API route.
    """
    print("test 1")
    model, cols, dfeat, safety = _artifacts()

    print("test 2")
    feat   = _feature_frame(patient, dfeat)
    scores = model.predict_proba(feat[cols])[:, 1]      # P(prescribe)

    rows = []
    for drug, score in zip(CATALOGUE, scores):
        a = safety.assess(drug, patient["egfr"])
        rows.append({
            "drug": drug,
            "ml_score": round(float(score), 3),
            "indication": dfeat[drug]["drug_indication"],
            "safety": a["status"],
            "dose_guidance": a["dose"],
            "reference": a["reference"],
        })

    df      = pd.DataFrame(rows).sort_values("ml_score", ascending=False)
    safe    = df[df["safety"] != "avoid"].head(top_k)
    removed = df[df["safety"] == "avoid"]

    return {
        "patient": {"egfr": patient["egfr"], "diagnoses": patient["diagnoses"]},
        "model": type(model.named_steps["clf"]).__name__,
        "suggestions": safe.to_dict(orient="records"),
        "removed":     removed.to_dict(orient="records"),
    }