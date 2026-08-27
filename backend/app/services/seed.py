"""Seed the local DB with synthetic patients — deterministic, safe to demo.

Generates raw serum creatinine (the real-world input) and runs it through the
same derivation used for imported data, so seeded patients carry eGFR, CrCl,
AKI stage and CKD stage exactly like real ones.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from app.core.renal_calc import (
    egfr_ckd_epi_2021, cockcroft_gault, aki_stages_for_series,
    ckd_stage, ckd_confirmed,
)
from app.models.db import Base, engine, SessionLocal, Patient, Lab, Drug

RENAL_DRUGS = ["metformin", "apixaban", "rivaroxaban", "enoxaparin", "gentamicin",
               "gabapentin", "ramipril", "sitagliptin", "nitrofurantoin",
               "digoxin", "lithium", "vancomycin"]
FIRST = ["Aisha", "Brian", "Chloe", "Dev", "Elena", "Farid", "Grace", "Hassan",
         "Isla", "Jacob", "Kavya", "Liam", "Maria", "Noah", "Priya", "Quinn",
         "Rosa", "Sam", "Tara", "Umar"]
LAST = ["Ahmed", "Brown", "Chen", "Das", "Evans", "Ferrari", "Gupta", "Hughes",
        "Ibrahim", "Jones", "Khan", "Lewis", "Martins", "Nolan", "Patel", "Reed"]


def seed(n_patients: int = 24, reset: bool = True) -> int:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    if s.query(Patient).count() > 0:
        s.close()
        return 0

    rng = np.random.default_rng(7)
    today = date(2025, 6, 1)

    for i in range(n_patients):
        age = int(rng.integers(52, 89))
        sex = "F" if rng.integers(0, 2) else "M"
        weight = round(float(rng.uniform(55, 95)), 1)
        height = round(float(rng.uniform(152, 185)), 1)

        # simulate a creatinine trajectory (the raw clinical input)
        n_labs = int(rng.integers(4, 8))
        base_scr = float(rng.uniform(0.8, 2.2))
        trend = float(rng.normal(0.25, 0.5))          # mg/dL per year
        days = np.sort(rng.integers(20, 900, n_labs))

        # ~1 in 6 patients gets an acute creatinine spike (to exercise AKI)
        spike_at = int(rng.integers(1, n_labs)) if rng.random() < 0.18 else -1

        readings = []
        for j, d in enumerate(days):
            scr = base_scr + trend * (d / 365.25) + float(rng.normal(0, 0.06))
            if j == spike_at:
                scr *= float(rng.uniform(1.8, 3.2))   # acute rise
            scr = float(np.clip(scr, 0.4, 11.0))
            readings.append((today - timedelta(days=int(900 - d)), round(scr, 2)))
        readings.sort(key=lambda t: t[0])

        egfrs = [egfr_ckd_epi_2021(scr, age, sex) for _, scr in readings]
        crcls = [cockcroft_gault(scr, age, sex, weight) for _, scr in readings]
        akis = aki_stages_for_series(readings)
        chronic = ckd_confirmed(list(zip([d for d, _ in readings], egfrs)))

        p = Patient(name=f"{FIRST[i % len(FIRST)]} {LAST[i % len(LAST)]}",
                    age=age, sex=sex, weight_kg=weight, height_cm=height,
                    ckd_confirmed=int(bool(chronic)),
                    ckd_stage=ckd_stage(egfrs[-1]))
        for (d, scr), eg, cr, ak in zip(readings, egfrs, crcls, akis):
            p.labs.append(Lab(measured_on=d, creatinine_mgdl=scr, egfr=eg,
                              crcl=cr, aki_stage=int(ak), ckd_stage=ckd_stage(eg)))
        for ing in rng.choice(RENAL_DRUGS, size=int(rng.integers(1, 4)), replace=False):
            p.drugs.append(Drug(ingredient=str(ing)))
        s.add(p)

    s.commit()
    count = s.query(Patient).count()
    s.close()
    return count


if __name__ == "__main__":
    print("seeded patients:", seed())
