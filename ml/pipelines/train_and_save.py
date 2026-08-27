"""Train the predictive layer and persist it to ml/models/model.joblib.

Once this file exists, the app loads it instead of the in-code fallback, so the
risk scores you show the supervisor come from a trained model.

Training source (in priority order):
  1. --features CSV  : a prepared table with the FEATURES columns + a label
  2. the app's SQLite DB : builds features from seeded/imported patients
  3. synthetic fallback  : same generator the app uses, so it always runs

The FEATURES list and order MUST match app/ml/model.py.
"""
from __future__ import annotations
import argparse, os, sqlite3
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, average_precision_score

FEATURES = ["window_last_egfr", "egfr_slope_per_year", "window_min_egfr",
            "n_renal_drugs", "age", "female"]
LABEL = "label"
OUT = os.getenv("MODEL_PATH", "ml/models/model.joblib")


def _slope(g):
    g = g.sort_values("measured_on")
    yrs = (g["measured_on"] - g["measured_on"].min()).dt.days / 365.25
    if len(g) < 2 or yrs.max() == 0:
        return 0.0
    return float(np.polyfit(yrs, g["egfr"], 1)[0])


def from_db(db_path):
    con = sqlite3.connect(db_path)
    labs = pd.read_sql("SELECT * FROM labs", con, parse_dates=["measured_on"])
    pts = pd.read_sql("SELECT * FROM patients", con)
    drugs = pd.read_sql("SELECT * FROM drugs", con)
    con.close()
    rows = []
    for pid, g in labs.groupby("patient_id"):
        g = g.sort_values("measured_on")
        p = pts[pts["id"] == pid].iloc[0]
        rows.append({
            "patient_id": pid,
            "window_last_egfr": g["egfr"].iloc[-1],
            "egfr_slope_per_year": _slope(g),
            "window_min_egfr": g["egfr"].min(),
            "n_renal_drugs": int((drugs["patient_id"] == pid).sum()),
            "age": int(p["age"]),
            "female": 1 if p["sex"] == "F" else 0,
            # label: latest eGFR below 45 (demo label; swap for the horizon-crossing
            # label from train_ml_layer.py on real longitudinal data)
            "label": int(g["egfr"].iloc[-1] < 45),
        })
    return pd.DataFrame(rows)


def synthetic(n=800):
    rng = np.random.default_rng(42)
    last = rng.uniform(20, 90, n); slope = rng.normal(-6, 12, n)
    mn = last - rng.uniform(0, 15, n); nd = rng.integers(1, 4, n)
    age = rng.integers(45, 90, n); fem = rng.integers(0, 2, n)
    logit = -0.09 * (last - 45) - 0.05 * slope + 0.35 * nd - 1.2
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    df = pd.DataFrame(dict(window_last_egfr=last, egfr_slope_per_year=slope,
                           window_min_egfr=mn, n_renal_drugs=nd, age=age,
                           female=fem, label=y))
    df["patient_id"] = np.arange(n)
    return df


def main(a):
    if a.features:
        df = pd.read_csv(a.features)
        src = f"features CSV ({a.features})"
    elif a.db and os.path.exists(a.db):
        df = from_db(a.db)
        src = f"app DB ({a.db})"
    else:
        df = synthetic()
        src = "synthetic fallback"
    print(f"training source: {src}  |  rows: {len(df)}  |  positives: {df[LABEL].mean():.1%}")

    X, y = df[FEATURES].fillna(0.0), df[LABEL].values
    groups = df.get("patient_id", pd.Series(range(len(df))))

    # held-out evaluation by patient group
    if len(df) >= 40 and len(np.unique(y)) > 1:
        tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=42)
                      .split(X, y, groups))
        m = GradientBoostingClassifier(random_state=42).fit(X.iloc[tr], y[tr])
        p = m.predict_proba(X.iloc[te])[:, 1]
        if len(np.unique(y[te])) > 1:
            print(f"held-out ROC AUC: {roc_auc_score(y[te], p):.3f} | "
                  f"PR AUC: {average_precision_score(y[te], p):.3f} "
                  f"(base {y[te].mean():.2f})")

    # fit final model on all data and persist
    model = GradientBoostingClassifier(random_state=42).fit(X, y)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    joblib.dump(model, OUT)
    print(f"saved model -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", help="CSV with FEATURES columns + 'label'")
    ap.add_argument("--db", default="backend/renal.db", help="app SQLite DB")
    main(ap.parse_args())
