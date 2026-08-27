#!/usr/bin/env python3
"""
Extract ONLY renal-relevant interactions from DDInter's class-split CSV files.

DDInter splits its downloads by ATC drug class (A, B, D, H, L, P, R, V) — there is
NO single "renal" file. Renal-relevant drugs are scattered across several class
files. This script reads whichever DDInter CSVs you've downloaded and keeps only the
pairs where at least one drug is in your renal drug list, writing them to
interactions.db for the app.

Download the CSVs first from https://ddinter.scbdd.com/download/ (you only really
need code_A and code_B for this project's drugs; grab more if you extend the list).

Usage:
    python filter_renal_ddinter.py --dir path/to/ddinter_csvs --out ../backend/interactions.db
"""
import argparse, glob, os, sqlite3
import pandas as pd

# the renal-relevant drugs this project cares about (extend as needed)
RENAL_DRUGS = {
    "metformin", "sitagliptin", "allopurinol",           # code_A (metabolism)
    "apixaban", "rivaroxaban", "dabigatran", "enoxaparin", "warfarin",  # code_B (blood)
    "ramipril", "lisinopril", "enalapril", "perindopril", # cardiovascular (check code availability)
    "digoxin", "spironolactone",
    "gabapentin", "pregabalin",                           # nervous system
    "gentamicin", "vancomycin", "nitrofurantoin",         # anti-infectives
    "lithium",
}


def main(a):
    files = glob.glob(os.path.join(a.dir, "ddinter_downloads_code_*.csv")) \
        or glob.glob(os.path.join(a.dir, "*.csv"))
    if not files:
        raise SystemExit(f"No DDInter CSVs found in {a.dir}. Download them from "
                         "https://ddinter.scbdd.com/download/ first.")

    frames = []
    for f in files:
        df = pd.read_csv(f)
        df.columns = [c.strip().lower() for c in df.columns]
        # DDInter columns: ddinterid_a, drug_a, ddinterid_b, drug_b, level
        da = next((c for c in df.columns if c in ("drug_a", "drug1", "name_a")), None)
        db = next((c for c in df.columns if c in ("drug_b", "drug2", "name_b")), None)
        lv = next((c for c in df.columns if c in ("level", "severity")), None)
        if not (da and db and lv):
            print(f"  skip {os.path.basename(f)} — columns {list(df.columns)}")
            continue
        df["_a"] = df[da].astype(str).str.lower().str.strip()
        df["_b"] = df[db].astype(str).str.lower().str.strip()
        # keep pair if EITHER drug is renal-relevant
        keep = df[df["_a"].isin(RENAL_DRUGS) | df["_b"].isin(RENAL_DRUGS)].copy()
        keep["severity"] = keep[lv].astype(str).str.strip().str.capitalize()
        frames.append(keep[["_a", "_b", "severity"]].rename(
            columns={"_a": "drug_a", "_b": "drug_b"}))
        print(f"  {os.path.basename(f)}: {len(keep)} renal-relevant pairs")

    if not frames:
        raise SystemExit("No usable rows found.")
    allp = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["drug_a", "drug_b"])

    con = sqlite3.connect(a.out)
    con.execute("DROP TABLE IF EXISTS ddinter")
    con.execute("CREATE TABLE ddinter (drug_a TEXT, drug_b TEXT, severity TEXT, "
                "interaction TEXT, management TEXT)")
    con.execute("CREATE INDEX idx_pair ON ddinter(drug_a, drug_b)")
    for _, r in allp.iterrows():
        con.execute("INSERT INTO ddinter VALUES (?,?,?,NULL,NULL)",
                    (r["drug_a"], r["drug_b"], r["severity"]))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM ddinter").fetchone()[0]
    sev = con.execute("SELECT severity, COUNT(*) FROM ddinter GROUP BY severity").fetchall()
    con.close()
    print(f"\nwrote {n} renal-relevant interactions -> {a.out}")
    print("by severity:", dict(sev))
    print("\nNote: DDInter downloads carry drug pairs + severity (Level). Mechanism/")
    print("management text is on the website per-pair, not always in the bulk CSVs.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder with downloaded DDInter CSVs")
    ap.add_argument("--out", default="../backend/interactions.db")
    main(ap.parse_args())
