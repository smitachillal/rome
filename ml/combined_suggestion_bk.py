"""
Combined suggestion pipeline — "ML proposes, rules dispose".

    patient -> [ML model ranks candidate drugs] -> [handbook safety filter] -> safe ranked list

The ML layer (prescribing_model) learns from real prescribing WHICH drugs suit a
patient like this. The handbook layer (handbook_safety) decides whether each is
renally SAFE at the patient's eGFR and attaches dose guidance + citation. The
model never overrides safety: a drug the handbook marks 'avoid' is removed no
matter how highly the model ranked it.

Run:
    python combined_suggestion.py                    # synthetic demo patient
    python combined_suggestion.py --source mimic --db ../../backend/renal.db
"""
from __future__ import annotations
import argparse
import numpy as np, pandas as pd

from prescribing_model import (CATALOGUE, DIAGNOSES, synth_cohort, load_from_db,
                               drug_features, build_matrix)
from handbook_safety import HandbookSafety


def train_ranker(patients, prescribed, dfeat):
    """Train the GB prescribing model; return (fitted_pipeline, feature_cols)."""
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.ensemble import GradientBoostingClassifier

    data = build_matrix(patients, prescribed, dfeat)
    cat = ["drug_class", "drug_indication"]
    num = [c for c in data.columns if c not in cat + ["label", "patient_id", "drug"]]
    pre = ColumnTransformer([("num", SimpleImputer(strategy="median"), num),
                             ("cat", OneHotEncoder(handle_unknown="ignore"), cat)])
    pipe = Pipeline([("pre", pre), ("clf", GradientBoostingClassifier(random_state=0))])
    pipe.fit(data[num + cat], data["label"])
    return pipe, num + cat


def suggest(patient, ranker, cols, dfeat, safety: HandbookSafety, top_k=8):
    """Produce the final ranked, renally-safe suggestion list for one patient."""
    # 1. ML proposes: score every catalogue drug for this patient
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

    # 2. Rules dispose: handbook safety verdict at this patient's eGFR
    out = []
    for drug, score in zip(CATALOGUE, scores):
        a = safety.assess(drug, patient["egfr"])
        out.append({
            "drug": drug, "ml_score": round(float(score), 3),
            "indication": dfeat[drug]["drug_indication"],
            "safety": a["status"], "dose_guidance": a["dose"],
            "reference": a["reference"],
        })
    df = pd.DataFrame(out).sort_values("ml_score", ascending=False)

    # 3. combine: drop 'avoid', keep the rest ranked; caution flagged
    safe = df[df["safety"] != "avoid"].head(top_k).reset_index(drop=True)
    removed = df[df["safety"] == "avoid"]
    return safe, removed


def main(a):
    dfeat = drug_features(a.handbook)
    safety = HandbookSafety(a.handbook)

    if a.source == "mimic":
        patients, prescribed = load_from_db(a.db)
        if not patients:
            raise SystemExit("No patients in DB — import MIMIC first.")
    else:
        patients, prescribed = synth_cohort(a.n)

    ranker, cols = train_ranker(patients, prescribed, dfeat)

    # demonstrate on a few patients
    import random; random.seed(1)
    picks = random.sample(patients, min(3, len(patients)))
    for p in picks:
        print("=" * 74)
        print(f"PATIENT {p['patient_id']}: age {p['age']}, "
              f"eGFR {p['egfr']}, CrCl {p['crcl']}, AKI {p['aki_stage']}, "
              f"CKD G{p['ckd_stage']}, dx={p['diagnoses']}")
        safe, removed = suggest(p, ranker, cols, dfeat, safety)
        print("\n  SUGGESTED (ML-ranked, renally screened):")
        print(f"  {'drug':15s}{'ml':>6s}  {'safety':8s} {'indication':16s} dose guidance")
        for _, r in safe.iterrows():
            tag = "OK" if r["safety"] == "normal" else r["safety"].upper()
            print(f"  {r['drug']:15s}{r['ml_score']:>6.2f}  {tag:8s} "
                  f"{r['indication']:16s} {r['dose_guidance'][:42]}")
        if len(removed):
            print("\n  REMOVED by handbook safety (eGFR too low):")
            for _, r in removed.iterrows():
                print(f"    {r['drug']:15s} — {r['dose_guidance'][:55]}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--handbook", default="/mnt/user-data/outputs/renal_drug_handbook_decision_tree_dataset.csv")
    ap.add_argument("--source", choices=["synthetic", "mimic"], default="synthetic")
    ap.add_argument("--db", default="../../backend/renal.db")
    ap.add_argument("--n", type=int, default=300)
    main(ap.parse_args())
