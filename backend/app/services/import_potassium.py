#!/usr/bin/env python3
"""
Import ONLY serum potassium from MIMIC labevents into labs.potassium_mmol_l.

NON-DESTRUCTIVE. This script never drops or recreates tables. It does not touch
patients, drugs, prescriptions or diagnoses — any manual edits you have made are
safe. It only:
    1. adds the potassium_mmol_l and k_flag columns to `labs` if they are missing
       (ALTER TABLE -- SQLAlchemy's create_all() will NOT add columns to an
       existing table, which is why this has to be done explicitly)
    2. UPDATEs existing labs rows with the potassium value for that patient/day
    3. optionally INSERTs rows for potassium-only draws (days with no creatinine)

MIMIC itemids:
    50971  Potassium, serum/plasma (chemistry)  -- preferred
    50822  Potassium, whole blood (blood gas)   -- fallback
MIMIC reports mEq/L, numerically identical to mmol/L for potassium.

Usage:
    python import_potassium.py --hosp path/to/hosp --db backend/renal.db
    python import_potassium.py --hosp path/to/hosp --db backend/renal.db --dry-run
    python import_potassium.py --hosp path/to/hosp --db backend/renal.db --no-insert
    python import_potassium.py --hosp path/to/hosp --db backend/renal.db --migrate-labs [this works]
"""
from __future__ import annotations
import argparse, glob, os, shutil, sqlite3, sys
import pandas as pd

POTASSIUM_ITEMIDS = [50971, 50822]      # first = preferred
CREATININE_ITEMID = 50912               # used only to align shifted dates
K_MIN, K_MAX = 1.5, 9.5                 # plausible mmol/L; outside = lab/entry error


def classify_k(k):
    """Same bands as the app's rule layer (inlined so this script stands alone)."""
    if k is None:
        return None
    if k >= 6.0:  return "severe_hyperkalaemia"
    if k >= 5.5:  return "hyperkalaemia"
    if k >= 5.0:  return "high_normal"
    if k <  3.0:  return "severe_hypokalaemia"
    if k <  3.5:  return "hypokalaemia"
    return "normal"



def egfr_is_not_null(con) -> bool:
    """Is labs.egfr declared NOT NULL? (blocks potassium-only inserts)"""
    for r in con.execute("PRAGMA table_info(labs)"):
        if r[1] == "egfr":
            return bool(r[3])          # r[3] = notnull flag
    return False


def migrate_labs_nullable_egfr(con):
    """Rebuild `labs` so egfr allows NULL, preserving every row and column.

    SQLite cannot drop a NOT NULL constraint in place, so the table is recreated:
    create a copy with the relaxed definition, copy the data across, swap names.
    Only `labs` is touched -- patients, drugs, prescriptions and diagnoses are not
    read or modified. A backup of the whole database is taken before this runs.
    """
    info = list(con.execute("PRAGMA table_info(labs)"))
    if not info:
        raise RuntimeError("no labs table")
    cols, defs = [], []
    for cid, name, ctype, notnull, dflt, pk in info:
        cols.append(name)
        d = f'"{name}" {ctype or "NUMERIC"}'
        if pk:
            d += " PRIMARY KEY"
        elif notnull and name != "egfr":     # relax ONLY egfr
            d += " NOT NULL"
        if dflt is not None:
            d += f" DEFAULT {dflt}"
        defs.append(d)
    collist = ", ".join(f'"{c}"' for c in cols)

    before = con.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
    con.commit()                      # close any implicit transaction first
    con.execute("PRAGMA foreign_keys=off")
    try:
        con.execute(f"CREATE TABLE labs_new ({', '.join(defs)})")
        con.execute(f"INSERT INTO labs_new ({collist}) SELECT {collist} FROM labs")
        moved = con.execute("SELECT COUNT(*) FROM labs_new").fetchone()[0]
        if moved != before:
            raise RuntimeError(f"row count mismatch: {before} -> {moved}, aborting")
        con.execute("DROP TABLE labs")
        con.execute("ALTER TABLE labs_new RENAME TO labs")
        con.commit()
    except Exception:
        con.rollback()
        con.execute("DROP TABLE IF EXISTS labs_new")
        con.commit()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=on")
    print(f"  labs table rebuilt with nullable egfr — {moved} rows preserved")


def _find(hosp, stem):
    hits = [h for h in glob.glob(os.path.join(hosp, stem + ".csv*")) if os.path.isfile(h)]
    if not hits:
        raise FileNotFoundError(f"{stem}.csv[.gz] not found in {hosp}")
    return hits[0]


def ensure_columns(con):
    """Add potassium columns to `labs` if absent. Existing data is untouched."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(labs)")]
    if not cols:
        sys.exit("No `labs` table found — is this the right database?")
    added = []
    if "potassium_mmol_l" not in cols:
        con.execute("ALTER TABLE labs ADD COLUMN potassium_mmol_l REAL")
        added.append("potassium_mmol_l")
    if "k_flag" not in cols:
        con.execute("ALTER TABLE labs ADD COLUMN k_flag TEXT")
        added.append("k_flag")
    con.commit()
    print(f"columns added: {added or '(already present)'}")


def load_potassium(hosp, keep_ids):
    """Read potassium (and creatinine, for date alignment) for the given patients."""
    frames, cr_frames = [], []
    wanted = POTASSIUM_ITEMIDS + [CREATININE_ITEMID]
    for ch in pd.read_csv(_find(hosp, "labevents"),
                          usecols=lambda c: c.lower() in
                          {"subject_id", "itemid", "charttime", "valuenum"},
                          chunksize=500_000, low_memory=False):
        ch.columns = [c.lower() for c in ch.columns]
        sel = ch[ch["itemid"].isin(wanted) & ch["subject_id"].isin(keep_ids)]
        if len(sel):
            frames.append(sel[sel["itemid"].isin(POTASSIUM_ITEMIDS)])
            cr_frames.append(sel[sel["itemid"] == CREATININE_ITEMID])
    csv_creat_max = None
    if cr_frames:
        cr = pd.concat(cr_frames, ignore_index=True)
        if len(cr):
            d = pd.to_datetime(cr["charttime"], errors="coerce").dropna()
            csv_creat_max = d.max().date() if len(d) else None
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame(columns=["subject_id", "day", "potassium_mmol_l"]), csv_creat_max

    k = pd.concat(frames, ignore_index=True).dropna(subset=["valuenum"])
    k = k[(k["valuenum"] >= K_MIN) & (k["valuenum"] <= K_MAX)]
    k["measured_on"] = pd.to_datetime(k["charttime"], errors="coerce")
    k = k.dropna(subset=["measured_on"])
    k["day"] = k["measured_on"].dt.date.astype(str)
    # prefer the chemistry assay when both exist on the same day
    k["pref"] = (k["itemid"] == POTASSIUM_ITEMIDS[0]).astype(int)
    k = (k.sort_values(["subject_id", "day", "pref"], ascending=[True, True, False])
           .drop_duplicates(subset=["subject_id", "day"], keep="first"))
    return (k[["subject_id", "day", "valuenum"]]
              .rename(columns={"valuenum": "potassium_mmol_l"}), csv_creat_max)


def main(a):
    if not os.path.exists(a.db):
        sys.exit(f"Database not found: {a.db}")

    con = sqlite3.connect(a.db)

    # make sure the target columns exist (ALTER TABLE, non-destructive)
    if not a.dry_run:
        ensure_columns(con)
    else:
        cols = [r[1] for r in con.execute("PRAGMA table_info(labs)")]
        missing = [c for c in ("potassium_mmol_l", "k_flag") if c not in cols]
        print(f"columns to add: {missing or '(already present)'}")

    # which patients are in this database? only import potassium for them
    pids = {r[0] for r in con.execute("SELECT id FROM patients")}
    if not pids:
        sys.exit("No patients in the database — import patients first.")
    print(f"patients in database: {len(pids)}")

    k, csv_creat_max = load_potassium(a.hosp, pids)
    print(f"potassium readings found for these patients: {len(k)}")
    if k.empty:
        print("Nothing to import.")
        return

    # existing lab rows, keyed by (patient, day)
    labs = pd.read_sql("SELECT id, patient_id, measured_on, potassium_mmol_l FROM labs", con)
    labs["day"] = labs["measured_on"].astype(str).str.slice(0, 10)
    # (patient, day) pairs that ALREADY hold a potassium value -- skip them so a
    # re-run updates in place rather than inserting duplicates.
    already = {(int(r.patient_id), r.day) for r in labs.itertuples(index=False)
               if pd.notna(r.potassium_mmol_l)}

    # ---- DATE ALIGNMENT ----------------------------------------------------
    # If the database dates were shifted (e.g. MIMIC's de-identified 2150 dates
    # moved to the present), the CSV's dates will not match. Detect the offset by
    # comparing the CSV's latest creatinine date with the database's latest lab
    # date, then shift the incoming potassium dates to match.
    # Anchor on rows that carry CREATININE only. Potassium-only rows inserted by a
    # previous run of this script must never influence the offset, or a re-run
    # would compute a bogus shift and duplicate every reading.
    anchor = pd.read_sql(
        "SELECT measured_on FROM labs WHERE creatinine_mgdl IS NOT NULL", con)
    if len(anchor):
        db_lab_max = pd.to_datetime(anchor["measured_on"].astype(str).str.slice(0, 10),
                                    errors="coerce").max()
    else:
        db_lab_max = pd.to_datetime(labs["day"], errors="coerce").max()
    offset_days = a.offset_days
    if offset_days is None and csv_creat_max is not None and pd.notna(db_lab_max):
        offset_days = (db_lab_max.date() - csv_creat_max).days
    offset_days = offset_days or 0
    print(f"date alignment: csv latest creatinine {csv_creat_max} | "
          f"db latest lab {db_lab_max.date() if pd.notna(db_lab_max) else None} "
          f"| offset {offset_days:+d} days")
    if offset_days:
        k["day"] = (pd.to_datetime(k["day"]) +
                    pd.Timedelta(days=offset_days)).dt.date.astype(str)
        print(f"  -> shifted incoming potassium dates by {offset_days:+d} days to align")
    existing = {(int(r.patient_id), r.day): int(r.id) for r in labs.itertuples(index=False)}

    # Match a potassium reading to a lab row on the SAME day, or within
    # --tolerance-days either side (a U&E panel and a creatinine may be recorded a
    # day apart after rounding/shifting). Nearest match wins; each lab row is used
    # at most once.
    from datetime import date as _date, timedelta as _td

    by_patient = {}
    for (pid, day), lab_id in existing.items():
        by_patient.setdefault(pid, []).append((_date.fromisoformat(day), lab_id))

    used, updates, inserts = set(), [], []
    tol = max(0, a.tolerance_days)
    for row in k.itertuples(index=False):
        pid, kday = int(row.subject_id), _date.fromisoformat(row.day)
        best, best_gap = None, None
        for lday, lab_id in by_patient.get(pid, []):
            if lab_id in used:
                continue
            gap = abs((lday - kday).days)
            if gap <= tol and (best_gap is None or gap < best_gap):
                best, best_gap = lab_id, gap
        if best is not None:
            used.add(best)
            updates.append((row.potassium_mmol_l, classify_k(row.potassium_mmol_l), best))
        elif (pid, row.day) not in already:
            inserts.append((pid, row.day, row.potassium_mmol_l,
                            classify_k(row.potassium_mmol_l)))

    print(f"  -> {len(updates)} existing lab rows will get a potassium value")
    print(f"  -> {len(inserts)} potassium-only days "
          f"({'will be inserted' if not a.no_insert else 'SKIPPED (--no-insert)'})")

    if a.dry_run:
        print("\n--dry-run: no changes written.")
        con.close()
        return

    if not a.no_backup:
        shutil.copy2(a.db, a.db + ".backup")
        print(f"\nbackup written: {a.db}.backup")

    con.executemany("UPDATE labs SET potassium_mmol_l = ?, k_flag = ? WHERE id = ?", updates)

    # potassium-only rows need a nullable egfr (no creatinine that day)
    if inserts and not a.no_insert and egfr_is_not_null(con):
        if a.migrate_labs:
            print("\nlabs.egfr is NOT NULL — migrating so potassium-only rows can be stored:")
            migrate_labs_nullable_egfr(con)
        else:
            print("\nSKIPPING the potassium-only inserts: labs.egfr is declared NOT NULL,")
            print("so a row with no creatinine cannot be stored. Two options:")
            print("  * re-run with --migrate-labs   (rebuilds ONLY the labs table so egfr")
            print("    allows NULL; all rows preserved, other tables untouched)")
            print("  * or re-run with --no-insert   (keep the updates, drop these readings)")
            inserts = []

    if inserts and not a.no_insert:
        con.executemany(
            "INSERT INTO labs (patient_id, measured_on, potassium_mmol_l, k_flag) "
            "VALUES (?, ?, ?, ?)", inserts)
    con.commit()

    n = con.execute("SELECT COUNT(*) FROM labs WHERE potassium_mmol_l IS NOT NULL").fetchone()[0]
    print(f"\nlabs rows now carrying potassium: {n}")
    print("band distribution:")
    for flag, cnt in con.execute(
            "SELECT k_flag, COUNT(*) FROM labs WHERE k_flag IS NOT NULL "
            "GROUP BY k_flag ORDER BY COUNT(*) DESC"):
        print(f"   {flag:22s} {cnt}")

    # prove nothing else was touched
    for t in ("patients", "drugs", "prescriptions", "diagnoses"):
        try:
            c = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t:14s} untouched: {c} rows")
        except sqlite3.Error:
            pass
    con.close()
    print("\nDone. Restart the backend to see the potassium panel populate.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosp", required=True, help="path to the MIMIC hosp/ folder")
    ap.add_argument("--db", default="backend/renal.db")
    ap.add_argument("--dry-run", action="store_true", help="preview only")
    ap.add_argument("--no-insert", action="store_true",
                    help="only update existing lab rows; skip potassium-only days")
    ap.add_argument("--tolerance-days", type=int, default=1,
                    help="match a potassium reading to a lab row within N days "
                         "(default 1; use 0 for exact-day only)")
    ap.add_argument("--offset-days", type=int, default=None,
                    help="manually shift incoming potassium dates by N days "
                         "(default: auto-detected from creatinine dates)")
    ap.add_argument("--migrate-labs", action="store_true",
                    help="rebuild the labs table so egfr allows NULL, enabling "
                         "potassium-only rows to be inserted (data preserved)")
    ap.add_argument("--no-backup", action="store_true")
    main(ap.parse_args())
