"""
python import_prescriptions.py --hosp ../../../scripts/mimic-iv-clinical-database-demo-2.2/mimic-iv-clinical-database-demo-2.2/hosp --db ../../renal.db

Import ONLY the raw MIMIC prescriptions table into a "prescriptions" SQLite table.

Standalone script -- no other project files needed. It creates its own patients
and prescriptions tables (patients minimal, just enough to satisfy the foreign
key) and loads every prescription row for the patients you import, unfiltered.

Usage:
    python import_prescriptions.py --hosp path/to/mimic-iv-demo/hosp --db renal.db
    python import_prescriptions.py --hosp path/to/hosp --db renal.db --limit 100
"""
from __future__ import annotations
import argparse, glob, os
import pandas as pd
from sqlalchemy import create_engine, Integer, String, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class PrescriptionDrugs(Base):
    __tablename__ = "prescriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    starttime: Mapped[str] = mapped_column(String)
    stoptime: Mapped[str] = mapped_column(String)
    drug_type: Mapped[str] = mapped_column(String)
    drug: Mapped[str] = mapped_column(String)
    prod_strength: Mapped[str] = mapped_column(String)
    dose_val_rx: Mapped[str] = mapped_column(String)
    dose_unit_rx: Mapped[str] = mapped_column(String)
    form_unit_disp: Mapped[str] = mapped_column(String)
    doses_per_24_hrs: Mapped[float] = mapped_column(Float, nullable=True)


def _find(hosp: str, stem: str) -> str:
    hits = [h for h in glob.glob(os.path.join(hosp, stem + ".csv*")) if os.path.isfile(h)]
    if not hits:
        raise FileNotFoundError(f"{stem}.csv[.gz] not found in {hosp}")
    return hits[0]


def _s(v) -> str:
    """Safe string coercion: NaN/None -> "" (not the literal string 'nan')."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)


def main(a):
    print(a.db)
    engine = create_engine(f"sqlite:///{a.db}")
    Base.metadata.create_all(engine)          # creates patients + prescriptions if missing
    Session = sessionmaker(bind=engine)
    s = Session()

    # 1. patients -- id MUST be the original MIMIC subject_id (not autoincrement),
    #    because prescriptions.subject_id foreign-keys to patients.id.
    print("path is " , a)
    pts = pd.read_csv(_find(a.hosp, "patients"))
    pts.columns = [c.lower() for c in pts.columns]
    if a.limit:
        pts = pts.head(a.limit)
    keep = set(pts["subject_id"].astype(int))

    existing = {p.id for p in s.query(Patient.id).all()}
    added_p = 0
    for sid in keep:
        if sid not in existing:
            s.add(Patient(id=int(sid)))
            added_p += 1
    s.commit()
    print(f"patients: {added_p} added, {len(keep)} total in scope")

    # 2. prescriptions -- every row, unfiltered, for these patients
    cols = {"subject_id", "drug", "starttime", "stoptime", "drug_type",
            "prod_strength", "dose_val_rx", "dose_unit_rx",
            "form_unit_disp", "doses_per_24_hrs"}
    rx = pd.read_csv(_find(a.hosp, "prescriptions"),
                     usecols=lambda c: c.lower() in cols)
    rx.columns = [c.lower() for c in rx.columns]
    rx = rx[rx["subject_id"].isin(keep)]
    print(f"prescriptions.csv rows for these patients: {len(rx)}")

    added_rx, skipped = 0, 0
    for r in rx.itertuples(index=False):
        sid = int(r.subject_id)
        if sid not in keep:            # belt-and-braces; should already be filtered
            skipped += 1
            continue
        s.add(PrescriptionDrugs(
            subject_id=sid,
            starttime=_s(getattr(r, "starttime", None)),
            stoptime=_s(getattr(r, "stoptime", None)),
            drug_type=_s(getattr(r, "drug_type", None)),
            drug=_s(getattr(r, "drug", None)),
            prod_strength=_s(getattr(r, "prod_strength", None)),
            dose_val_rx=_s(getattr(r, "dose_val_rx", None)),
            dose_unit_rx=_s(getattr(r, "dose_unit_rx", None)),
            form_unit_disp=_s(getattr(r, "form_unit_disp", None)),
            doses_per_24_hrs=(float(r.doses_per_24_hrs)
                              if pd.notna(getattr(r, "doses_per_24_hrs", None)) else None),
        ))
        added_rx += 1
    s.commit()

    n = s.query(PrescriptionDrugs).count()
    print(f"prescriptions inserted this run: {added_rx}  (skipped: {skipped})")
    print(f"prescriptions table now has: {n} rows total")
    s.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosp", required=True, help="path to the MIMIC hosp/ folder")
    ap.add_argument("--db", default="renal.db", help="SQLite database file")
    ap.add_argument("--limit", type=int, default=None, help="limit number of patients")
    main(ap.parse_args())
