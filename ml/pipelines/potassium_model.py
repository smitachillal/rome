#!/usr/bin/env python3
"""
Potassium breach prediction (Proposal 2) — hyperkalaemia AND hypokalaemia.

TASK. From a patient's serial potassium, renal function and potassium-affecting
drug burden, predict whether their NEXT potassium measurement will breach an
action threshold (>= 5.5 or < 3.5 mmol/L).

THE PLANNED ABLATION (the proposal's "known risk"). Serum potassium and renal
function are strongly correlated, so a model may simply relearn eGFR. This is
tested head-on by training three feature sets and comparing AUC:

    A. renal only    — eGFR, CKD stage, creatinine
    B. renal + K+    — adds the patient's own potassium history
    C. full          — adds the potassium-affecting DRUG burden

If C > B > A, the drug features add signal beyond kidney function, which is the
claim the proposal needs to defend. Reported per model, not asserted.

Run:
    python potassium_model.py                       # synthetic cohort
    python potassium_model.py --source db --db ../../backend/renal.db
"""
from __future__ import annotations
import argparse, sys, os
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
from potassium import K_DRUGS, RAISING, LOWERING, is_breach, classify_k

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, accuracy_score, f1_score

FEATURE_SETS = {
    "A. renal only":  ["egfr", "creatinine", "ckd_stage_ord", "age"],
    "B. renal + K+":  ["egfr", "creatinine", "ckd_stage_ord", "age",
                       "k_last", "k_mean", "k_slope", "k_max", "k_min"],
    "C. full (+drugs)": ["egfr", "creatinine", "ckd_stage_ord", "age",
                         "k_last", "k_mean", "k_slope", "k_max", "k_min",
                         "n_raising", "n_lowering", "raising_burden",
                         "lowering_burden", "net_k_burden"],
}


def synth_cohort(n=500, seed=42):
    """Synthetic patients whose potassium follows real clinical logic.

    K+ is driven by: baseline, renal impairment (poor excretion -> higher K+),
    and net drug burden (raising agents push up, lowering agents push down),
    plus noise. This lets the ablation demonstrate that drug burden carries
    signal the renal features alone cannot express.
    """
    rng = np.random.default_rng(seed)
    rows = []
    raising_pool = sorted(RAISING)
    lowering_pool = sorted(LOWERING)
    for pid in range(n):
        age = int(rng.integers(45, 90))
        egfr = float(np.clip(rng.normal(55, 25), 6, 120))
        creat = round(float(np.clip(120 / max(egfr, 5), 0.5, 9)), 2)
        ckd = min(5, max(1, int(np.ceil((120 - egfr) / 22))))

        n_r = int(rng.choice([0, 1, 2, 3], p=[0.35, 0.30, 0.22, 0.13]))
        n_l = int(rng.choice([0, 1, 2], p=[0.45, 0.38, 0.17]))
        r_drugs = list(rng.choice(raising_pool, size=n_r, replace=False)) if n_r else []
        l_drugs = list(rng.choice(lowering_pool, size=n_l, replace=False)) if n_l else []
        r_burden = sum(K_DRUGS[d][1] for d in r_drugs)
        l_burden = sum(K_DRUGS[d][1] for d in l_drugs)
        net = r_burden - l_burden

        # potassium history: renal impairment raises it, net drug burden shifts it
        base = 4.2 + (60 - min(egfr, 60)) * 0.012 + net * 0.13
        hist = [float(np.clip(base + rng.normal(0, 0.28), 2.2, 7.5)) for _ in range(4)]
        # the NEXT reading -> the label
        nxt = float(np.clip(base + net * 0.05 + rng.normal(0, 0.34), 2.2, 7.8))

        x = np.arange(len(hist))
        slope = float(np.polyfit(x, hist, 1)[0]) if len(hist) > 1 else 0.0
        rows.append({
            "patient_id": pid, "age": age, "egfr": round(egfr, 1), "creatinine": creat,
            "ckd_stage_ord": ckd,
            "k_last": round(hist[-1], 2), "k_mean": round(float(np.mean(hist)), 2),
            "k_slope": round(slope, 3), "k_max": round(max(hist), 2),
            "k_min": round(min(hist), 2),
            "n_raising": n_r, "n_lowering": n_l,
            "raising_burden": r_burden, "lowering_burden": l_burden,
            "net_k_burden": net,
            "raising_drugs": ",".join(r_drugs), "lowering_drugs": ",".join(l_drugs),
            "k_next": round(nxt, 2),
            "label": int(is_breach(nxt)),
            "breach_type": classify_k(nxt) if is_breach(nxt) else "none",
        })
    return pd.DataFrame(rows)


def load_from_db(db_path):
    """Build the same feature frame from the app database (real data path)."""
    import sqlite3
    con = sqlite3.connect(db_path)
    labs = pd.read_sql("SELECT * FROM labs", con, parse_dates=["measured_on"])
    pts = pd.read_sql("SELECT * FROM patients", con)
    drugs = pd.read_sql("SELECT patient_id, ingredient FROM drugs", con)
    con.close()
    if "potassium_mmol_l" not in labs.columns or labs["potassium_mmol_l"].notna().sum() == 0:
        raise SystemExit("No potassium data in labs — import serum potassium first "
                         "(MIMIC labevents itemid 50971).")
    ck = {"G1":1,"G2":2,"G3a":3,"G3b":4,"G4":5,"G5":5}
    rx = drugs.groupby("patient_id")["ingredient"].apply(list).to_dict()
    rows = []
    for _, p in pts.iterrows():
        pid = int(p["id"])
        g = labs[(labs["patient_id"] == pid) & labs["potassium_mmol_l"].notna()] \
            .sort_values("measured_on")
        if len(g) < 3:            # need history + a next reading to predict
            continue
        hist = g["potassium_mmol_l"].tolist()
        nxt = hist[-1]; hist = hist[:-1]
        meds = [str(x).lower() for x in rx.get(pid, [])]
        r = [d for d in meds if d in RAISING]; l = [d for d in meds if d in LOWERING]
        x = np.arange(len(hist))
        rows.append({
            "patient_id": pid, "age": int(p["age"]),
            "egfr": float(g["egfr"].iloc[-1]) if pd.notna(g["egfr"].iloc[-1]) else np.nan,
            "creatinine": float(g["creatinine_mgdl"].iloc[-1]) if pd.notna(g["creatinine_mgdl"].iloc[-1]) else np.nan,
            "ckd_stage_ord": ck.get(str(p.get("ckd_stage") or ""), 3),
            "k_last": hist[-1], "k_mean": float(np.mean(hist)),
            "k_slope": float(np.polyfit(x, hist, 1)[0]) if len(hist) > 1 else 0.0,
            "k_max": max(hist), "k_min": min(hist),
            "n_raising": len(r), "n_lowering": len(l),
            "raising_burden": sum(K_DRUGS[d][1] for d in r),
            "lowering_burden": sum(K_DRUGS[d][1] for d in l),
            "net_k_burden": sum(K_DRUGS[d][1] for d in r) - sum(K_DRUGS[d][1] for d in l),
            "raising_drugs": ",".join(r), "lowering_drugs": ",".join(l),
            "k_next": nxt, "label": int(is_breach(nxt)),
            "breach_type": classify_k(nxt) if is_breach(nxt) else "none",
        })
    return pd.DataFrame(rows)


def models():
    return {
        "Baseline": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "Random Forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0),
        "Gradient Boosting": GradientBoostingClassifier(random_state=0),
    }


def evaluate(data):
    y = data["label"]; groups = data["patient_id"]
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=42).split(data, y, groups))
    results = []
    for set_name, feats in FEATURE_SETS.items():
        X = data[feats]
        for m_name, clf in models().items():
            pipe = Pipeline([("imp", SimpleImputer(strategy="median")), ("clf", clf)])
            pipe.fit(X.iloc[tr], y.iloc[tr])
            pred = pipe.predict(X.iloc[te])
            try:
                proba = pipe.predict_proba(X.iloc[te])[:, 1]
                auc = roc_auc_score(y.iloc[te], proba) if y.iloc[te].nunique() > 1 else np.nan
                pr = average_precision_score(y.iloc[te], proba)
            except Exception:
                auc = pr = np.nan
            results.append({"features": set_name, "model": m_name,
                            "accuracy": accuracy_score(y.iloc[te], pred),
                            "f1": f1_score(y.iloc[te], pred, zero_division=0),
                            "roc_auc": auc, "pr_auc": pr})
    return pd.DataFrame(results), (tr, te)



def build_features_for_patient(patient_row: dict) -> dict:
    """Shape one patient's data into the model's feature vector (shared with the API)."""
    return {k: patient_row.get(k) for k in FEATURE_SETS["C. full (+drugs)"]}


def save_bundle(data, out_path):
    """Train the best model (by ROC-AUC, on the full feature set) on ALL data and
    save it so the API can serve live predictions without retraining."""
    import joblib, os
    res, _ = evaluate(data)
    res = res.dropna(subset=["roc_auc"])
    best = res[res["features"] == "C. full (+drugs)"].sort_values(
        "roc_auc", ascending=False).iloc[0]
    feats = FEATURE_SETS["C. full (+drugs)"]
    clf = models()[best["model"]]
    pipe = Pipeline([("imp", SimpleImputer(strategy="median")), ("clf", clf)])
    pipe.fit(data[feats], data["label"])       # refit on everything for deployment
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    joblib.dump({"model": pipe, "features": feats, "model_name": best["model"],
                 "metrics": {k: float(best[k]) for k in
                             ("roc_auc", "pr_auc", "accuracy", "f1")},
                 "thresholds": {"high": 5.5, "low": 3.5}}, out_path)
    print(f"saved potassium model ({best['model']}) -> {out_path}")
    print(f"   ROC-AUC {best['roc_auc']:.3f}  PR-AUC {best['pr_auc']:.3f}")
    return pipe, feats, best


def export_metrics(data, res, out_json):
    """Write the full ablation grid + curves + importance for the dashboard."""
    import json
    from sklearn.metrics import roc_curve, precision_recall_curve, confusion_matrix
    y = data["label"]; groups = data["patient_id"]
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=42).split(data, y, groups))

    best_row = res.dropna(subset=["roc_auc"]).sort_values("roc_auc", ascending=False).iloc[0]
    feats = FEATURE_SETS[best_row["features"]]
    pipe = Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("clf", models()[best_row["model"]])]).fit(data[feats].iloc[tr], y.iloc[tr])
    proba = pipe.predict_proba(data[feats].iloc[te])[:, 1]
    fpr, tpr, _ = roc_curve(y.iloc[te], proba)
    prec, rec, _ = precision_recall_curve(y.iloc[te], proba)
    step = max(1, len(fpr) // 60)

    imp = []
    clf = pipe.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        imp = sorted(({"feature": f, "importance": round(float(v), 4)}
                      for f, v in zip(feats, clf.feature_importances_)),
                     key=lambda d: -d["importance"])[:12]

    a_best = float(res[res["features"] == "A. renal only"]["roc_auc"].max())
    c_best = float(res[res["features"] == "C. full (+drugs)"]["roc_auc"].max())

    payload = {
        "task": "Potassium breach at next reading (K+ >= 5.5 or < 3.5 mmol/L)",
        "n_patients": int(len(data)),
        "breach_rate": float(data["label"].mean()),
        "breach_types": data[data["label"] == 1]["breach_type"].value_counts().to_dict(),
        "feature_sets": {k: v for k, v in FEATURE_SETS.items()},
        "results": json.loads(res.to_json(orient="records")),
        "ablation": {"renal_only_auc": a_best, "full_auc": c_best,
                     "gain": round(c_best - a_best, 3)},
        "best": {"model": best_row["model"], "features": best_row["features"],
                 "roc_auc": float(best_row["roc_auc"]), "pr_auc": float(best_row["pr_auc"]),
                 "accuracy": float(best_row["accuracy"]), "f1": float(best_row["f1"])},
        "curves_best": {"roc": {"fpr": [round(float(v), 3) for v in fpr[::step]],
                                "tpr": [round(float(v), 3) for v in tpr[::step]]},
                        "pr": {"recall": [round(float(v), 3) for v in rec[::step]],
                               "precision": [round(float(v), 3) for v in prec[::step]]}},
        "confusion_best": confusion_matrix(y.iloc[te], pipe.predict(data[feats].iloc[te])).tolist(),
        "feature_importance": imp,
    }
    with open(out_json, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"metrics written -> {out_json}")


def main(a):
    data = synth_cohort(a.n) if a.source == "synthetic" else load_from_db(a.db)
    tag = "SYNTHETIC" if a.source == "synthetic" else "REAL (DB)"
    print(f"{tag} cohort: {len(data)} patients | breach rate: {data['label'].mean():.1%}")
    print("breach types:", data[data['label'] == 1]['breach_type'].value_counts().to_dict())

    res, _ = evaluate(data)
    print("\n=== ABLATION: does drug burden add signal beyond renal function? ===")
    piv = res.pivot(index="model", columns="features", values="roc_auc").round(3)
    print(piv.to_string())

    best = res.dropna(subset=["roc_auc"]).sort_values("roc_auc", ascending=False).iloc[0]
    print(f"\nbest: {best['model']} on '{best['features']}' — "
          f"ROC-AUC {best['roc_auc']:.3f}, PR-AUC {best['pr_auc']:.3f}")

    if a.metrics_json:
        export_metrics(data, res, a.metrics_json)
    if a.save_model:
        save_bundle(data, a.save_model)

    a_best = res[res["features"] == "A. renal only"]["roc_auc"].max()
    c_best = res[res["features"] == "C. full (+drugs)"]["roc_auc"].max()
    print(f"\nrenal-only best AUC : {a_best:.3f}")
    print(f"full-model best AUC : {c_best:.3f}")
    print(f"gain from K+ history and drug burden: {c_best - a_best:+.3f}")
    if c_best - a_best < 0.02:
        print("  -> drug features add little beyond renal function. Report this honestly;")
        print("     it is a real finding, not a failure.")
    else:
        print("  -> drug features add signal beyond kidney function alone.")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "db"], default="synthetic")
    ap.add_argument("--db", default="../../backend/renal.db")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--metrics-json", default=None, help="export dashboard metrics JSON")
    ap.add_argument("--save-model", default=None, help="save the deployable model bundle")
    main(ap.parse_args())
