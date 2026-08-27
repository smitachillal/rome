"""Import patient data into the app's SQLite DB and derive all renal parameters.

Two input modes:

  --mode simple : tidy CSVs you control (see docs/DATA_IMPORT.md)
        patients.csv : id,name,age,sex[,weight_kg,height_cm]
        labs.csv     : patient_id,measured_on,creatinine_mgdl
                       (or creatinine_umol_l, or a pre-computed egfr)
        drugs.csv    : patient_id,ingredient
        weights.csv  : (optional) patient_id,weight_kg

  --mode mimic  : MIMIC-IV `hosp` directory
        patients.csv[.gz]      -> demographics
        labevents.csv[.gz]     -> serum creatinine (itemid 50912)
        prescriptions.csv[.gz] -> drugs, matched to the curated set
        omr.csv[.gz]           -> weight (for CrCl)

Whatever the source, every row goes through the SAME derivation step
(`_derive_and_store`), which computes and persists:

    creatinine -> eGFR (CKD-EPI 2021)
               -> CrCl (Cockcroft-Gault, needs weight)
               -> AKI stage (KDIGO, creatinine route)
               -> CKD G-category  (+ patient-level chronicity flag)

Usage:
    python -m app.services.import_csv --mode simple --path /path/to/csv_folder
    python -m app.services.import_csv --mode mimic  --path /path/to/hosp --limit 100
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

from app.core.renal_calc import (
    egfr_ckd_epi_2021, cockcroft_gault, aki_stages_for_series,
    ckd_stage, ckd_confirmed, umol_to_mgdl,
)
# from app.models.db import Base, engine, SessionLocal, Patient, Lab, Drug, Diagnosis

from app.models.db import Base, engine, SessionLocal, Patient, Lab, Drug, PrescriptionDrugs

CURATED = {"metformin", "apixaban", "rivaroxaban", "enoxaparin", "gentamicin",
           "gabapentin", "ramipril", "lisinopril", "enalapril", "perindopril",
           "sitagliptin", "nitrofurantoin", "digoxin", "lithium", "vancomycin",
           "spironolactone", "allopurinol", "morphine", "methotrexate",
           "dabigatran", "pregabalin", "warfarin"}

CREATININE_ITEMID = 50912          # MIMIC-IV serum creatinine

# ICD-9/10 code prefixes -> clinical diagnosis category. Prefix match on the code
# with dots removed. This mapping is deliberately coarse (a real limitation): it
# infers *why a drug might be needed* from coded conditions, which is imperfect.
ICD_CATEGORY_RULES = [
    ("diabetes",        ["E10", "E11", "E12", "E13", "E14", "250"]),
    ("hypertension",    ["I10", "I11", "I12", "I13", "I15", "401", "402", "403", "404", "405"]),
    ("heart_failure",   ["I50", "428"]),
    # anticoagulation is a need, proxied by AF / VTE diagnoses
    ("anticoagulation", ["I48", "42731", "I26", "I80", "I82", "4151", "4534"]),
    ("infection",       ["A41", "J18", "J15", "N39", "N10", "A40", "038", "486", "5990", "590"]),
    ("gout",            ["M10", "274"]),
    ("pain",            ["G629", "M79", "G563", "3565", "7291"]),   # neuropathic pain proxies
]


def map_icd_to_category(code: str) -> str | None:
    if not isinstance(code, str):
        return None
    c = code.upper().replace(".", "").strip()
    for category, prefixes in ICD_CATEGORY_RULES:
        if any(c.startswith(p) for p in prefixes):
            return category
    return None




# --------------------------------------------------------------------------
# shared derivation + persistence
# --------------------------------------------------------------------------
# def _derive_and_store(people: pd.DataFrame, labs: pd.DataFrame,
#                       drugs: pd.DataFrame,
#                       diagnoses: pd.DataFrame | None = None) -> dict:

def _derive_and_store(people: pd.DataFrame, labs: pd.DataFrame,
                         drugs: pd.DataFrame,
                         raw_prescriptions: "pd.DataFrame | None" = None) -> dict:
    """Compute all four parameters and write patients/labs/drugs to SQLite.

    Expected columns
      people : id, name, age, sex, weight_kg (nullable), height_cm (nullable)
      labs   : patient_id, measured_on (datetime), creatinine_mgdl, egfr (nullable)
      drugs  : patient_id, ingredient
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()

    stats = {"patients": 0, "labs": 0, "drugs": 0, "diagnoses": 0,
             "crcl_computed": 0, "aki_flagged": 0, "ckd_confirmed": 0}

    people = people.drop_duplicates(subset=["id"]).set_index("id")
    labs = labs.sort_values(["patient_id", "measured_on"])

    for pid, prow in people.iterrows():
        age = float(prow["age"])
        sex = str(prow["sex"])
        weight = prow.get("weight_kg")
        weight = None if (weight is None or pd.isna(weight)) else round(float(weight), 1)
        height = prow.get("height_cm")
        height = None if (height is None or pd.isna(height)) else float(height)

        g = labs[labs["patient_id"] == pid]
        if g.empty:
            continue

        # ---- 1 & 2: eGFR and CrCl, per reading ----
        rows = []
        for _, r in g.iterrows():
            scr = r.get("creatinine_mgdl")
            scr = None if (scr is None or pd.isna(scr)) else float(scr)

            egfr = r.get("egfr")
            egfr = None if (egfr is None or pd.isna(egfr)) else float(egfr)
            if egfr is None and scr is not None:
                egfr = egfr_ckd_epi_2021(scr, age, sex)

            crcl = cockcroft_gault(scr, age, sex, weight) if scr is not None else None
            if crcl is not None:
                stats["crcl_computed"] += 1

            rows.append({"measured_on": r["measured_on"], "scr": scr,
                         "egfr": egfr, "crcl": crcl})

        # ---- 3: AKI stage across the series ----
        aki = aki_stages_for_series([(x["measured_on"], x["scr"]) for x in rows]) \
            if any(x["scr"] is not None for x in rows) else [0] * len(rows)

        # ---- 4: CKD category per reading + chronicity for the patient ----
        chronic = ckd_confirmed([(x["measured_on"], x["egfr"]) for x in rows])
        latest_egfr = next((x["egfr"] for x in reversed(rows) if x["egfr"] is not None), None)

        s.add(Patient(id=int(pid), name=str(prow["name"]), age=int(age),
                      sex=sex[0], weight_kg=weight, height_cm=height,
                      ckd_confirmed=int(bool(chronic)),
                      ckd_stage=ckd_stage(latest_egfr)))
        stats["patients"] += 1
        if chronic:
            stats["ckd_confirmed"] += 1
        s.flush()

        for x, stage in zip(rows, aki):
            if x["egfr"] is None:
                continue
            if stage > 0:
                stats["aki_flagged"] += 1
            s.add(Lab(patient_id=int(pid),
                      measured_on=pd.to_datetime(x["measured_on"]).date(),
                      creatinine_mgdl=x["scr"], egfr=x["egfr"], crcl=x["crcl"],
                      aki_stage=int(stage), ckd_stage=ckd_stage(x["egfr"])))
            stats["labs"] += 1

    dcols = ["patient_id", "ingredient"]
    has_dates = "start_date" in drugs.columns
    if has_dates:
        dcols += ["start_date", "end_date"]
    for row in drugs[dcols].drop_duplicates().itertuples(index=False):
        if int(row.patient_id) in people.index:
            kw = {}
            if has_dates:
                sd = getattr(row, "start_date", None)
                ed = getattr(row, "end_date", None)
                kw["start_date"] = None if pd.isna(sd) else sd
                kw["end_date"] = None if pd.isna(ed) else ed
            s.add(Drug(patient_id=int(row.patient_id),
                       ingredient=str(row.ingredient).lower(), **kw))
            stats["drugs"] += 1

    if diagnoses is not None and len(diagnoses):
        seen = set()
        for row in diagnoses[["patient_id", "icd_code", "category"]].itertuples(index=False):
            pid = int(row.patient_id)
            key = (pid, row.category)
            if pid in people.index and key not in seen and row.category:
                s.add(Diagnosis(patient_id=pid, icd_code=str(row.icd_code),
                                category=str(row.category)))
                seen.add(key)
                stats["diagnoses"] = stats.get("diagnoses", 0) + 1

    s.commit()
    s.close()
    return stats


# --------------------------------------------------------------------------
# simple CSV mode
# --------------------------------------------------------------------------
def import_simple(folder: str) -> dict:
    people = pd.read_csv(f"{folder}/patients.csv")
    people.columns = [c.lower() for c in people.columns]
    for opt in ("weight_kg", "height_cm"):
        if opt not in people.columns:
            people[opt] = np.nan

    labs = pd.read_csv(f"{folder}/labs.csv", parse_dates=["measured_on"])
    labs.columns = [c.lower() for c in labs.columns]
    if "creatinine_mgdl" not in labs.columns:
        if "creatinine_umol_l" in labs.columns:
            labs["creatinine_mgdl"] = labs["creatinine_umol_l"].apply(
                lambda v: None if pd.isna(v) else umol_to_mgdl(float(v)))
        else:
            labs["creatinine_mgdl"] = np.nan
    if "egfr" not in labs.columns:
        labs["egfr"] = np.nan

    drugs = pd.read_csv(f"{folder}/drugs.csv")
    drugs.columns = [c.lower() for c in drugs.columns]
    # optional medication timeline. Accepts start_date/end_date (or start/end,
    # or started_on/stopped_on). Missing end_date = still being taken (current);
    # missing BOTH = unknown timeline, which interaction checks treat
    # conservatively (included, and shown as "NO DATES" in the UI).
    _alias = {"start": "start_date", "started_on": "start_date", "from": "start_date",
              "end": "end_date", "stopped_on": "end_date", "stop_date": "end_date",
              "to": "end_date"}
    drugs = drugs.rename(columns={k: v for k, v in _alias.items() if k in drugs.columns})
    for col in ("start_date", "end_date"):
        if col in drugs.columns:
            drugs[col] = pd.to_datetime(drugs[col], errors="coerce").dt.date
        else:
            drugs[col] = None

    # optional weights.csv overrides / supplies weight
    wpath = os.path.join(folder, "weights.csv")
    if os.path.exists(wpath):
        w = pd.read_csv(wpath)
        w.columns = [c.lower() for c in w.columns]
        wmap = dict(zip(w["patient_id"].astype(int), w["weight_kg"].astype(float)))
        people["weight_kg"] = people["id"].astype(int).map(wmap).fillna(people["weight_kg"])

    return _derive_and_store(people, labs, drugs)


# --------------------------------------------------------------------------
# MIMIC-IV mode
# --------------------------------------------------------------------------
def _find(hosp: str, stem: str) -> str:
    """Locate <stem>.csv or <stem>.csv.gz, returning a readable FILE path.

    Guards against two common failure modes:
      * the extraction produced a DIRECTORY named e.g. "patients.csv" — globbing
        would match it and pandas would fail (PermissionError on Windows,
        IsADirectoryError on Linux);
      * the file is open in Excel / another program, which locks it on Windows
        and also surfaces as PermissionError.
    """
    print("hosp ->", hosp)
    hits = glob.glob(os.path.join(hosp, stem + ".csv*"))
    files = [h for h in hits if os.path.isfile(h)]
    dirs = [h for h in hits if os.path.isdir(h)]
    print(dirs)
    print(files)
    if not files:
        if dirs:
            raise FileNotFoundError(
                f"'{os.path.basename(dirs[0])}' in {hosp} is a FOLDER, not a file.\n"
                f"         The archive was probably extracted with a tool that made a\n"
                f"         directory per file. Look inside it for the real "
                f"{stem}.csv/.csv.gz and point --path at the folder that holds the\n"
                f"         actual files, or re-extract the zip.")
        raise FileNotFoundError(
            f"{stem}.csv[.gz] not found in {hosp}\n"
            f"         Files present: "
            f"{', '.join(sorted(os.listdir(hosp))[:12]) if os.path.isdir(hosp) else '(path is not a directory)'}")

    # prefer a plain .csv, then .csv.gz, then whatever matched
    for pref in (stem + ".csv", stem + ".csv.gz"):
        for f in files:
            if os.path.basename(f).lower() == pref:
                return _check_readable(f)
    return _check_readable(files[0])


def _check_readable(path: str) -> str:
    """Fail early with an actionable message if the file cannot be opened."""
    try:
        with open(path, "rb") as fh:
            fh.read(1)
    except PermissionError as e:
        raise PermissionError(
            f"Cannot read {path}\n"
            f"         [Errno 13] Permission denied. On Windows this usually means:\n"
            f"           1. the file is OPEN IN EXCEL (or another program) - close it;\n"
            f"           2. it is actually a folder, not a file;\n"
            f"           3. the file is read-protected / blocked after download\n"
            f"              (right-click > Properties > Unblock).") from e
    return path


def _omr_weights(hosp: str, keep: set) -> dict:
    """Median weight (kg) per patient from OMR; falls back to weights.csv."""
    wpath = os.path.join(hosp, "weights.csv")
    if os.path.exists(wpath):
        w = pd.read_csv(wpath)
        w.columns = [c.lower() for c in w.columns]
        return {int(r["subject_id"]): float(r["weight_kg"])
                for _, r in w.iterrows() if int(r["subject_id"]) in keep}
    try:
        omr = pd.read_csv(_find(hosp, "omr"))
    except FileNotFoundError:
        return {}
    omr.columns = [c.lower() for c in omr.columns]
    w = omr[omr["result_name"].str.contains("weight", case=False, na=False)].copy()
    w = w[w["subject_id"].isin(keep)]
    if w.empty:
        return {}
    w["val"] = pd.to_numeric(w["result_value"], errors="coerce")
    is_lbs = w["result_name"].str.contains("lb", case=False, na=False)
    w["kg"] = np.where(is_lbs, w["val"] * 0.453592, w["val"])
    return w.dropna(subset=["kg"]).groupby("subject_id")["kg"].median().to_dict()


def import_mimic(hosp: str, limit: int | None = None) -> dict:
    pts = pd.read_csv(_find(hosp, "patients"))
    pts.columns = [c.lower() for c in pts.columns]
    pts = pts[["subject_id", "gender", "anchor_age", "anchor_year"]]
    if limit:
        pts = pts.head(limit)
    keep = set(pts["subject_id"])
    weights = _omr_weights(hosp, keep)

    # serum creatinine
    frames = []
    for ch in pd.read_csv(_find(hosp, "labevents"),
                          usecols=lambda c: c.lower() in
                          {"subject_id", "itemid", "charttime", "valuenum"},
                          chunksize=500_000, low_memory=False):
        ch.columns = [c.lower() for c in ch.columns]
        sel = ch[(ch["itemid"] == CREATININE_ITEMID) & (ch["subject_id"].isin(keep))]
        if len(sel):
            frames.append(sel)
    if not frames:
        raise SystemExit("No serum creatinine (itemid 50912) rows found.")
    lab = pd.concat(frames, ignore_index=True).dropna(subset=["valuenum"])
    lab = lab[(lab["valuenum"] > 0) & (lab["valuenum"] < 40)]
    lab = lab.merge(pts, on="subject_id")
    lab["measured_on"] = pd.to_datetime(lab["charttime"], errors="coerce")
    lab = lab.dropna(subset=["measured_on"])
    # age at the time of the test
    lab["age_at"] = lab["anchor_age"] + (lab["measured_on"].dt.year - lab["anchor_year"])

    labs = pd.DataFrame({
        "patient_id": lab["subject_id"].astype(int),
        "measured_on": lab["measured_on"],
        "creatinine_mgdl": lab["valuenum"].astype(float),
        "egfr": np.nan,          # derived centrally
    })

    people = pd.DataFrame({
        "id": pts["subject_id"].astype(int),
        "name": ["Patient " + str(s) for s in pts["subject_id"]],
        "age": pts["anchor_age"].astype(int),
        "sex": pts["gender"].astype(str),
        "weight_kg": pts["subject_id"].map(weights),
        "height_cm": np.nan,
    })

    rx = pd.read_csv(_find(hosp, "prescriptions"),
                     usecols=lambda c: c.lower() in {"subject_id", "drug",
                                                     "starttime", "stoptime"})
    rx.columns = [c.lower() for c in rx.columns]
    rx = rx[rx["subject_id"].isin(keep)].copy()
    rx["ingredient"] = rx["drug"].str.lower().str.extract(
        r"(" + "|".join(sorted(CURATED, key=len, reverse=True)) + r")", expand=False)
    rx = rx.dropna(subset=["ingredient"]).rename(columns={"subject_id": "patient_id"})
    # medication timeline: MIMIC prescriptions carry starttime/stoptime.
    # A NULL stoptime is treated as "still being taken" (current).
    for src, dst in (("starttime", "start_date"), ("stoptime", "end_date")):
        if src in rx.columns:
            rx[dst] = pd.to_datetime(rx[src], errors="coerce").dt.date
        else:
            rx[dst] = None
    drugs = rx[["patient_id", "ingredient", "start_date", "end_date"]]

    # diagnoses: map ICD codes -> clinical categories
    diagnoses = None
    try:
        dx = pd.read_csv(_find(hosp, "diagnoses_icd"),
                         usecols=lambda c: c.lower() in {"subject_id", "icd_code", "icd_version"})
        dx.columns = [c.lower() for c in dx.columns]
        dx = dx[dx["subject_id"].isin(keep)].copy()
        dx["category"] = dx["icd_code"].astype(str).map(map_icd_to_category)
        dx = dx.dropna(subset=["category"])
        diagnoses = dx.rename(columns={"subject_id": "patient_id"})[
            ["patient_id", "icd_code", "category"]]
    except FileNotFoundError:
        pass   # diagnoses_icd is optional; dx_* features will be zero without it

    return _derive_and_store(people, labs, drugs, diagnoses)


def main(a):
    stats = import_simple(a.path) if a.mode == "simple" else import_mimic(a.path, a.limit)
    print(f"Imported from {a.mode}: {a.path}")
    for k, v in stats.items():
        print(f"  {k:16s} {v}")
    if stats["crcl_computed"] == 0:
        print("  NOTE: no CrCl computed (no weight found) — CrCl-dosed drugs "
              "will fall back to eGFR.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["simple", "mimic"], default="simple")
    ap.add_argument("--path", required=True)
    ap.add_argument("--limit", type=int, default=None)
    main(ap.parse_args())
