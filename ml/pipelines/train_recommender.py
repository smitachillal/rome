"""
Train the drug-recommender and SAVE it for the app to serve.

Bundles three things into one joblib file so the backend has everything it needs
to make a recommendation without retraining:
    - the fitted ML ranker (best model)
    - the feature-column order it expects
    - the per-drug handbook features

Usage:
    python train_recommender.py                              # synthetic
    python train_recommender.py --source mimic --db ../../backend/renal.db
    python train_recommender.py --out ../../backend/ml/recommender.joblib
"""
from __future__ import annotations
import argparse, os
import joblib

from prescribing_model import (CATALOGUE, DIAGNOSES, synth_cohort, load_from_db,
                               drug_features, build_matrix)
from evaluate_helpers import train_best      # small shared helper (below)


def main(a):
    dfeat = drug_features(a.handbook)
    if a.source == "mimic":
        patients, prescribed = load_from_db(a.db)
        if not patients:
            raise SystemExit("No patients in DB — import MIMIC first.")
    else:
        patients, prescribed = synth_cohort(a.n)

    ranker, cols, best_name, metrics = train_best(patients, prescribed, dfeat)

    bundle = {
        "ranker": ranker,
        "feature_cols": cols,
        "drug_features": dfeat,
        "catalogue": dict(CATALOGUE),
        "diagnoses": list(DIAGNOSES),
        "best_model": best_name,
        "metrics": metrics,
        "handbook_csv": a.handbook,
    }
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    joblib.dump(bundle, a.out)
    print(f"saved recommender ({best_name}) -> {a.out}")
    print(f"   ROC-AUC {metrics['roc_auc']:.3f}  precision@1 {metrics['precision_at_1']:.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--handbook", default="../data/renal_drug_handbook_decision_tree_dataset.csv")
    ap.add_argument("--source", choices=["synthetic", "mimic"], default="synthetic")
    ap.add_argument("--db", default="../../backend/renal.db")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="../../backend/ml/recommender.joblib")
    main(ap.parse_args())
