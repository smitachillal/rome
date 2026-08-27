"""
Combined suggestion pipeline — "ML proposes, rules dispose" — MULTI-MODEL.

Trains several ML rankers, evaluates and compares them (classification + ranking
metrics), then uses the best one to produce renally-safe, handbook-screened drug
suggestions. Also writes a metrics JSON for a dashboard UI.

    patient -> [ML ranker] -> [handbook safety filter] -> safe ranked suggestion

Run:
    python combined_suggestion.py                         # synthetic demo
    python combined_suggestion.py --source mimic --db ../../backend/renal.db
    python combined_suggestion.py --metrics-json metrics.json   # export for dashboard
"""
from __future__ import annotations
import argparse, json
import numpy as np, pandas as pd

from prescribing_model import (CATALOGUE, DIAGNOSES, synth_cohort, load_from_db,
                               drug_features, build_matrix)
from handbook_safety import HandbookSafety

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                              ExtraTreesClassifier)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                             average_precision_score, precision_score, recall_score,
                             confusion_matrix, roc_curve, precision_recall_curve)
import os
import joblib

def make_models():
    """The candidate ML rankers to compare."""
    return {
        "Baseline":            DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(max_iter=100, class_weight="balanced"),
        "Naive Bayes":         GaussianNB(),
        "K-Nearest Neighbours":KNeighborsClassifier(n_neighbors=15),
        "Decision Tree":       DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=0),
        "Random Forest":       RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0),
        "Extra Trees":         ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=0),
        "Gradient Boosting":   GradientBoostingClassifier(random_state=0),
    }


def _prep(data):
    cat = ["drug_class", "drug_indication"]
    num = [c for c in data.columns if c not in cat + ["label", "patient_id", "drug"]]
    pre = ColumnTransformer([("num", SimpleImputer(strategy="median"), num),
                             ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])
    return pre, num + cat


def precision_at_k(data_te, proba, k):
    """Mean precision@k over patients: of the top-k suggested drugs, how many prescribed."""
    tmp = data_te.copy(); tmp["p"] = proba
    vals = []
    for _, g in tmp.groupby("patient_id"):
        if g["label"].sum() == 0:
            continue
        top = g.sort_values("p", ascending=False).head(k)
        vals.append(top["label"].mean())
    return float(np.mean(vals)) if vals else float("nan")


def evaluate_all(patients, prescribed, dfeat):
    """Train every model, compute metrics, return (results, fitted, split, data)."""
    data = build_matrix(patients, prescribed, dfeat)
    pre, cols = _prep(data)
    X, y, groups = data[cols], data["label"], data["patient_id"]
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=42).split(X, y, groups))
    data_te = data.iloc[te]

    results, fitted = [], {}
    for name, clf in make_models().items():
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X.iloc[tr], y.iloc[tr])
        pred = pipe.predict(X.iloc[te])
        try:
            proba = pipe.predict_proba(X.iloc[te])[:, 1]
        except Exception:
            proba = pred.astype(float)
        row = {
            "model": name,
            "accuracy": accuracy_score(y.iloc[te], pred),
            "precision": precision_score(y.iloc[te], pred, zero_division=0),
            "recall": recall_score(y.iloc[te], pred, zero_division=0),
            "f1": f1_score(y.iloc[te], pred, zero_division=0),
            "roc_auc": roc_auc_score(y.iloc[te], proba) if len(set(y.iloc[te])) > 1 else float("nan"),
            "pr_auc": average_precision_score(y.iloc[te], proba),
            "precision_at_1": precision_at_k(data_te, proba, 1),
            "precision_at_3": precision_at_k(data_te, proba, 3),
            "confusion": confusion_matrix(y.iloc[te], pred).tolist(),
        }
        results.append(row); fitted[name] = pipe
    return pd.DataFrame(results), fitted, (tr, te), data, cols


def curve_points(pipe, data, split, cols):
    """ROC and PR curve points for the given fitted model (for the dashboard)."""
    tr, te = split
    y = data["label"].iloc[te]
    proba = pipe.predict_proba(data[cols].iloc[te])[:, 1]
    fpr, tpr, _ = roc_curve(y, proba)
    prec, rec, _ = precision_recall_curve(y, proba)
    step = max(1, len(fpr)//60)
    return {"roc": {"fpr": fpr[::step].round(3).tolist(), "tpr": tpr[::step].round(3).tolist()},
            "pr": {"recall": rec[::step].round(3).tolist(), "precision": prec[::step].round(3).tolist()}}


def suggest(patient, ranker, cols, dfeat, safety, top_k=8):
    rows = []
    for drug in CATALOGUE:
        rows.append({
            "age": patient["age"], "sex": patient["sex"], "weight_kg": patient["weight_kg"],
            "egfr": patient["egfr"], "crcl": patient["crcl"],
            "aki_stage": patient["aki_stage"], "ckd_stage": patient["ckd_stage"],
            "n_existing_drugs": patient["n_existing_drugs"],
            **{f"dx_{dx}": int(dx in patient["diagnoses"]) for dx in DIAGNOSES},
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
        a = safety.assess(drug, patient["egfr"])
        out.append({"drug": drug, "ml_score": round(float(score), 3),
                    "indication": dfeat[drug]["drug_indication"], "safety": a["status"],
                    "dose_guidance": a["dose"], "reference": a["reference"]})
    df = pd.DataFrame(out).sort_values("ml_score", ascending=False)
    return df[df["safety"] != "avoid"].head(top_k).reset_index(drop=True), df[df["safety"] == "avoid"]


def main(a):
    dfeat = drug_features(a.handbook)
    safety = HandbookSafety(a.handbook)
    if a.source == "mimic":
        patients, prescribed = load_from_db(a.db)
        if not patients: raise SystemExit("No patients in DB — import MIMIC first.")
    else:
        patients, prescribed = synth_cohort(a.n)

    results, fitted, split, data, cols = evaluate_all(patients, prescribed, dfeat)
    results = results.sort_values("roc_auc", ascending=False).reset_index(drop=True)

    print("=== MODEL COMPARISON ===")
    show = results[["model","accuracy","f1","roc_auc","pr_auc","precision_at_1","precision_at_3"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    best_name = results.iloc[0]["model"]
    print(f"\nbest by ROC-AUC: {best_name}  -> used for suggestions")
    best = fitted[best_name]

    # export dashboard metrics
    if a.metrics_json:
        payload = {
            "source": a.source,
            "n_patients": len(patients),
            "n_prescriptions": len(prescribed),
            "models": json.loads(results.drop(columns=["confusion"]).to_json(orient="records")),
            "confusion_best": results[results["model"]==best_name]["confusion"].iloc[0],
            "curves_best": curve_points(best, data, split, cols),
            "feature_importance": _importance(best, cols),
            "best_model": best_name,
            "catalogue": CATALOGUE,
            "diagnoses": DIAGNOSES
            # "ml_score": ml_score
        }
        with open(a.metrics_json, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"metrics written -> {a.metrics_json}")


    # save the model in joblib
    OUT = os.getenv("MODEL_PATH", "../models/model_gb.joblib")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    joblib.dump(best, OUT)
    print(f"saved model -> {OUT}")

    # a couple of worked suggestions
    import random; random.seed(1)
    for p in random.sample(patients, min(2, len(patients))):
        safe, removed = suggest(p, best, cols, dfeat, safety)
        print(f"\nPATIENT {p['patient_id']}: eGFR {p['egfr']}, dx={p['diagnoses']}")
        for _, r in safe.head(5).iterrows():
            tag = "OK" if r["safety"]=="normal" else r["safety"].upper()
            print(f"  {r['drug']:15s} ml={r['ml_score']:.2f} [{tag}] {r['dose_guidance'][:40]}")
        for _, r in removed.iterrows():
            print(f"  REMOVED {r['drug']} — {r['dose_guidance'][:45]}")


def _importance(pipe, cols):
    """Feature importance / coefficients from the best model, if available."""
    clf = pipe.named_steps["clf"]
    try:
        names = pipe.named_steps["pre"].get_feature_names_out()
    except Exception:
        names = cols
    if hasattr(clf, "feature_importances_"):
        imp = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        imp = np.abs(clf.coef_).ravel()
    else:
        return []
    pairs = sorted(zip(names, imp), key=lambda t: -t[1])[:12]
    return [{"feature": str(n).replace("num__","").replace("cat__",""),
             "importance": round(float(v), 4)} for n, v in pairs]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--handbook", default="../data/renal_drug_handbook_decision_tree_dataset.csv")
    ap.add_argument("--source", choices=["synthetic","mimic"], default="synthetic")
    ap.add_argument("--db", default="../../backend/renal.db")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--metrics-json", default=None, help="write dashboard metrics JSON")
    main(ap.parse_args())
