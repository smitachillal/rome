#!/usr/bin/env python3
"""
Prescribing-suggestion model (Framing #2) — patient conditions -> drug suggestion.

FRAMING. For each (patient, candidate-drug) pair, predict whether the drug was
prescribed. Scoring every candidate for a patient and ranking them yields a
DRUG SUGGESTION list. This combines PATIENT features (renal state, demographics,
diagnosis, existing drugs) with DRUG features (from the Renal Drug Handbook CSV).

DATA. Runs on a synthetic cohort by default (clearly labelled) whose prescribing
follows real clinical logic: a drug is prescribed when its indication matches the
patient's diagnosis AND it is not renally contraindicated at the patient's eGFR
(plus noise). Swap `--source mimic --db renal.db` to use real data: patients and
their prescribed drugs come from the app DB, prescriptions become the labels.

>>> On synthetic data the accuracy only shows the pipeline can RECOVER a known
    rule. Real clinical accuracy requires real MIMIC prescriptions. <<<

USAGE:
    pip install pandas numpy scikit-learn matplotlib
    python prescribing_model.py                     # synthetic demo
    python prescribing_model.py --n 400
"""
import argparse, json, re
import numpy as np, pandas as pd

# ---------------------------------------------------------------- drug catalogue
# curated renally-relevant drugs: name -> (class, indication, renal_avoid_egfr)
# renal_avoid_egfr = eGFR below which the drug is contraindicated/avoided
CATALOGUE = {
    "metformin":     ("biguanide",        "diabetes",        30),
    "sitagliptin":   ("dpp4",             "diabetes",        15),
    "ramipril":      ("ace_inhibitor",    "hypertension",    15),
    "lisinopril":    ("ace_inhibitor",    "hypertension",    15),
    "enalapril":     ("ace_inhibitor",    "heart_failure",   15),
    "apixaban":      ("doac",             "anticoagulation", 15),
    "rivaroxaban":   ("doac",             "anticoagulation", 15),
    "dabigatran":    ("doac",             "anticoagulation", 30),
    "enoxaparin":    ("lmwh",             "anticoagulation", 15),
    "digoxin":       ("cardiac_glycoside","heart_failure",   10),
    "gabapentin":    ("gabapentinoid",    "pain",            10),
    "pregabalin":    ("gabapentinoid",    "pain",            10),
    "gentamicin":    ("aminoglycoside",   "infection",       10),
    "nitrofurantoin":("nitrofuran",       "infection",       45),
    "vancomycin":    ("glycopeptide",     "infection",       10),
    "allopurinol":   ("xanthine_oxidase", "gout",            10),
    "spironolactone":("k_sparing",        "heart_failure",   30),
}
DIAGNOSES = ["diabetes","hypertension","heart_failure","anticoagulation","infection","pain","gout"]
HANDBOOK_NAME = {  # curated -> handbook Drug_name for feature join
    "metformin":"Metformin hydrochloride","sitagliptin":"Sitagliptin","ramipril":"Ramipril",
    "lisinopril":"Lisinopril","enalapril":"Enalapril maleate","apixaban":"Apixaban",
    "rivaroxaban":"Rivaroxaban","dabigatran":"Dabigatran etexilate","enoxaparin":"Enoxaparin sodium",
    "digoxin":"Digoxin","gabapentin":"Gabapentin","pregabalin":"Pregabalin","gentamicin":"Gentamicin",
    "nitrofurantoin":"Nitrofurantoin","vancomycin":"Vancomycin","allopurinol":"Allopurinol",
    "spironolactone":"Spironolactone",
}


def _num(x):
    if not isinstance(x, str): return np.nan
    m = re.search(r"-?\d+\.?\d*", x.replace("–", "-"))
    return float(m.group()) if m else np.nan


def drug_features(handbook_csv):
    """Per-drug features pulled from the handbook CSV, keyed by curated name."""
    df = pd.read_csv(handbook_csv)
    idx = {r["Drug_name"]: r for _, r in df.iterrows()}
    feats = {}
    for cur, hb in HANDBOOK_NAME.items():
        row = idx.get(hb)
        pk = {}
        if row is not None:
            try: pk = json.loads(row["ml_params_for_AI"]).get("renal_pharmacokinetic_features", {}) or {}
            except Exception: pk = {}
        cls, indic, avoid = CATALOGUE[cur]
        feats[cur] = {
            "drug_class": cls,
            "drug_indication": indic,
            "drug_pct_excreted": _num(pk.get("urinary_excretion_unchanged")),
            "drug_half_life": _num(pk.get("half_life")),
            "drug_protein_binding": _num(pk.get("protein_binding")),
        }
    return feats


def synth_cohort(n, seed=42):
    """Synthetic patients + prescriptions following real clinical logic."""
    rng = np.random.default_rng(seed)
    patients = []
    for pid in range(n):
        age = int(rng.integers(45, 90))
        sex = int(rng.integers(0, 2))                 # 1 = female
        weight = round(float(rng.uniform(55, 95)), 1)
        egfr = round(float(np.clip(rng.normal(55, 25), 6, 120)), 1)
        crcl = round(egfr * float(rng.uniform(0.8, 1.3)), 1)
        aki = int(rng.choice([0, 1, 2, 3], p=[0.75, 0.12, 0.08, 0.05]))
        ckd = min(5, max(1, int(np.ceil((120 - egfr) / 22))))    # rough G-stage
        dx = list(rng.choice(DIAGNOSES, size=int(rng.integers(1, 3)), replace=False))
        patients.append(dict(patient_id=pid, age=age, sex=sex, weight_kg=weight,
                             egfr=egfr, crcl=crcl, aki_stage=aki, ckd_stage=ckd,
                             diagnoses=dx))
    # generate prescriptions with clinical logic
    rx = []
    for p in patients:
        n_existing = 0
        for drug, (cls, indic, avoid) in CATALOGUE.items():
            match = indic in p["diagnoses"]
            safe = p["egfr"] >= avoid
            prescribe = 0
            if match and safe and rng.random() < 0.85:      # right drug, safe -> usually given
                prescribe = 1
            elif match and not safe and rng.random() < 0.15: # unsafe -> occasionally still given
                prescribe = 1
            elif (not match) and rng.random() < 0.03:        # off-indication noise
                prescribe = 1
            if prescribe:
                rx.append((p["patient_id"], drug)); n_existing += 1
        p["n_existing_drugs"] = n_existing
    return patients, set(rx)


def build_matrix(patients, prescribed, dfeat, neg_ratio=3, seed=1):
    """Assemble (patient x candidate-drug) examples with label = prescribed."""
    rng = np.random.default_rng(seed)
    rows = []
    drugs = list(CATALOGUE)
    for p in patients:
        pos = [d for d in drugs if (p["patient_id"], d) in prescribed]
        neg = [d for d in drugs if d not in pos]
        rng.shuffle(neg)
        keep = set(pos) | set(neg[:max(len(pos) * neg_ratio, 3)])
        for d in keep:
            f = {
                "patient_id": p["patient_id"], "drug": d,
                "age": p["age"], "sex": p["sex"], "weight_kg": p["weight_kg"],
                "egfr": p["egfr"], "crcl": p["crcl"],
                "aki_stage": p["aki_stage"], "ckd_stage": p["ckd_stage"],
                "n_existing_drugs": p["n_existing_drugs"],
                **{f"dx_{dx}": int(dx in p["diagnoses"]) for dx in DIAGNOSES},
                "drug_pct_excreted": dfeat[d]["drug_pct_excreted"],
                "drug_half_life": dfeat[d]["drug_half_life"],
                "drug_protein_binding": dfeat[d]["drug_protein_binding"],
                "drug_class": dfeat[d]["drug_class"],
                "drug_indication": dfeat[d]["drug_indication"],
                "label": int((p["patient_id"], d) in prescribed),
            }
            rows.append(f)
    return pd.DataFrame(rows)


def main(a):
    from sklearn.model_selection import GroupShuffleSplit
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                                 average_precision_score, classification_report)

    patients, prescribed = synth_cohort(a.n)
    dfeat = drug_features(a.handbook)
    data = build_matrix(patients, prescribed, dfeat)
    print(f"SYNTHETIC cohort: {len(patients)} patients, {len(prescribed)} prescriptions")
    print(f"training examples (patient x drug): {len(data)}  "
          f"prescribed rate: {data['label'].mean():.1%}\n")

    cat = ["drug_class", "drug_indication"]
    num = [c for c in data.columns if c not in cat + ["label", "patient_id", "drug"]]
    pre = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), num),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
    ])
    X = data[num + cat]; y = data["label"]; groups = data["patient_id"]
    tr, te = next(GroupShuffleSplit(1, test_size=0.25, random_state=42).split(X, y, groups))

    models = {
        "Baseline (never prescribe)": DummyClassifier(strategy="constant", constant=0),
        "Logistic Regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
        "Decision Tree (d5)": DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=0),
        "Random Forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=0),
        "Gradient Boosting": GradientBoostingClassifier(random_state=0),
    }
    print(f"{'model':28s}{'accuracy':>10s}{'F1(presc)':>11s}{'ROC-AUC':>9s}{'PR-AUC':>8s}")
    fitted = {}
    for name, clf in models.items():
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X.iloc[tr], y.iloc[tr])
        pred = pipe.predict(X.iloc[te])
        acc = accuracy_score(y.iloc[te], pred)
        f1 = f1_score(y.iloc[te], pred, zero_division=0)
        try:
            prob = pipe.predict_proba(X.iloc[te])[:, 1]
            auc = roc_auc_score(y.iloc[te], prob); pr = average_precision_score(y.iloc[te], prob)
        except Exception:
            auc = pr = float("nan")
        print(f"{name:28s}{acc:>10.3f}{f1:>11.3f}{auc:>9.3f}{pr:>8.3f}")
        fitted[name] = pipe

    # ---- ranking quality: precision@k per patient ----
    best = fitted["Gradient Boosting"]
    test_pids = data.iloc[te]["patient_id"].unique()
    p_at_1 = p_at_3 = cnt = 0
    for pid in test_pids:
        sub = data[data["patient_id"] == pid]
        if sub["label"].sum() == 0: continue
        prob = best.predict_proba(sub[num + cat])[:, 1]
        order = sub.assign(prob=prob).sort_values("prob", ascending=False)
        p_at_1 += order.head(1)["label"].mean()
        p_at_3 += order.head(3)["label"].mean()
        cnt += 1
    print(f"\nRanking quality (Gradient Boosting):  "
          f"precision@1 = {p_at_1/cnt:.3f}   precision@3 = {p_at_3/cnt:.3f}")

    # 1. structure
    print("boosting rounds :", best.named_steps)
    # print("classes         :", list(best.classes_))
    # print("trees total     :", best.estimators_.size, "(rounds x classes)")
    # print("depth per tree  :", best.max_depth)
    

    # ---- worked example: suggest drugs for one test patient ----
    pid = test_pids[0]
    p = next(x for x in patients if x["patient_id"] == pid)
    sub = data[data["patient_id"] == pid].copy()
    sub["score"] = best.predict_proba(sub[num + cat])[:, 1]
    print(f"\n=== SUGGESTION for patient {pid} "
          f"(age {p['age']}, eGFR {p['egfr']}, dx={p['diagnoses']}) ===")
    show = sub.sort_values("score", ascending=False)[["drug", "score", "label"]].head(6)
    show["prescribed?"] = show["label"].map({1: "YES", 0: "-"})
    print(show[["drug", "score", "prescribed?"]].to_string(index=False))

    pid = test_pids[1]
    p = next(x for x in patients if x["patient_id"] == pid)
    sub = data[data["patient_id"] == pid].copy()
    sub["score"] = best.predict_proba(sub[num + cat])[:, 1]
    print(f"\n=== SUGGESTION for patient {pid} "
        f"(age {p['age']}, eGFR {p['egfr']}, dx={p['diagnoses']}) ===")
    show = sub.sort_values("score", ascending=False)[["drug", "score", "label"]].head(6)
    show["prescribed?"] = show["label"].map({1: "YES", 0: "-"})
    print(show[["drug", "score", "prescribed?"]].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    # WORKING CODE
    # ap.add_argument("--handbook", default="./data/renal_drug_handbook_decision_tree_dataset.csv")
    # ap.add_argument("--n", type=int, default=500, help="synthetic patients")
    

    ap.add_argument("--handbook", default="./data/prescriptions.csv")
    ap.add_argument("--n", type=int, default=500, help="synthetic patients")

    #CODE COMMENTS
    # ap.add_argument("--handbook", default="./data/renal_drug_handbook_decision_tree_dataset.csv")
    # ap.add_argument("--n", type=int, default=300, help="synthetic patients")
    # ap.add_argument("--source", choices=["synthetic", "mimic"], default="synthetic",
    #                 help="where patient data comes from")

    # ap.add_argument("--db", default="./backend/renal.db",
    #                 help="app SQLite DB (used when --source mimic)")
    
    main(ap.parse_args())
