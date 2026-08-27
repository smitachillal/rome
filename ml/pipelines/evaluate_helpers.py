"""Shared: train all models, evaluate, return the best fitted ranker."""
from __future__ import annotations
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, accuracy_score
from prescribing_model import build_matrix
from combined_suggestion import make_models, _prep, precision_at_k


def train_best(patients, prescribed, dfeat):
    data = build_matrix(patients, prescribed, dfeat)
    pre, cols = _prep(data)
    X, y, groups = data[cols], data["label"], data["patient_id"]
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=42).split(X, y, groups))
    from sklearn.pipeline import Pipeline
    best, best_auc, best_name, best_metrics = None, -1, None, {}
    for name, clf in make_models().items():
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X.iloc[tr], y.iloc[tr])
        try:
            proba = pipe.predict_proba(X.iloc[te])[:, 1]
        except Exception:
            continue
        auc = roc_auc_score(y.iloc[te], proba) if len(set(y.iloc[te])) > 1 else 0
        if auc > best_auc:
            pred = pipe.predict(X.iloc[te])
            best, best_auc, best_name = pipe, auc, name
            best_metrics = {
                "roc_auc": float(auc),
                "pr_auc": float(average_precision_score(y.iloc[te], proba)),
                "accuracy": float(accuracy_score(y.iloc[te], pred)),
                "f1": float(f1_score(y.iloc[te], pred, zero_division=0)),
                "precision_at_1": float(precision_at_k(data.iloc[te], proba, 1)),
                "precision_at_3": float(precision_at_k(data.iloc[te], proba, 3)),
            }
    # refit best on ALL data for deployment
    best.fit(X, y)
    return best, cols, best_name, best_metrics
