"""Predictive layer.

Loads a persisted gradient-boosted-tree model and exposes per-patient risk with
a SHAP-style attribution. If no model file exists yet (fresh checkout), a small
in-memory model is trained on the seeded synthetic features so the app always
runs. Real deployments load ml/models/model.joblib produced by the training
pipeline.
"""
from __future__ import annotations
import os
from functools import lru_cache
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

try:
    import joblib
    from sklearn.ensemble import GradientBoostingClassifier
except Exception:  # pragma: no cover
    joblib = None

FEATURES = [
    "window_last_egfr", "egfr_slope_per_year", "window_min_egfr",
    "n_renal_drugs", "age", "female",
]
MODEL_PATH = os.getenv("MODEL_PATH", "ml/models/model.joblib")


def _train_fallback():
    """Deterministic synthetic training so risk scores are sensible without a file."""
    rng = np.random.default_rng(42)
    n = 600
    last = rng.uniform(20, 90, n)
    slope = rng.normal(-6, 12, n)
    mn = last - rng.uniform(0, 15, n)
    ndrugs = rng.integers(1, 4, n)
    age = rng.integers(45, 90, n)
    female = rng.integers(0, 2, n)
    X = np.column_stack([last, slope, mn, ndrugs, age, female])
    # ground-truth-ish rule: low + falling + polypharmacy -> breach
    logit = (-0.09 * (last - 45)) + (-0.05 * slope) + 0.35 * ndrugs - 1.2
    p = 1 / (1 + np.exp(-logit))
    y = (rng.uniform(size=n) < p).astype(int)
    m = GradientBoostingClassifier(random_state=42).fit(X, y)
    return m


@lru_cache(maxsize=1)
def get_model():
    if joblib and os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return _train_fallback()


def predict_risk(feat: dict) -> float:
    x = pd.DataFrame([[feat[f] for f in FEATURES]], columns=FEATURES)
    return float(get_model().predict_proba(x)[0, 1])


def explain(feat: dict) -> list[dict]:
    """SHAP attribution if available; else signed feature deltas as a fallback."""
    xdf = pd.DataFrame([[feat[f] for f in FEATURES]], columns=FEATURES)
    x = xdf.values
    model = get_model()
    try:
        import shap
        sv = shap.TreeExplainer(model).shap_values(xdf)[0]
    except Exception:
        # fallback: importance x centred value (keeps the UI populated)
        imp = getattr(model, "feature_importances_", np.ones(len(FEATURES)))
        sv = imp * (x[0] - x[0].mean())
    out = [{"feature": f, "contribution": float(sv[i]), "value": float(x[0][i])}
           for i, f in enumerate(FEATURES)]
    out.sort(key=lambda d: abs(d["contribution"]), reverse=True)
    return out
