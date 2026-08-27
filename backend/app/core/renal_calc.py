"""Renal parameter calculations — the single source of truth for all four metrics.

Every parameter the system stores is computed here, from raw serum creatinine:

  1. eGFR   — CKD-EPI 2021 (race-free)      -> mL/min/1.73m^2
  2. CrCl   — Cockcroft-Gault                -> mL/min  (needs weight)
  3. AKI    — KDIGO stage (creatinine route)  -> 0/1/2/3
  4. CKD    — KDIGO GFR category (G1..G5)     -> label + chronicity check

CLINICAL NOTE. eGFR equations assume steady-state renal function. During AKI
creatinine lags the true GFR, so eGFR/CrCl are unreliable — which is exactly why
AKI is computed and stored alongside them. The rule layer can then suppress or
caveat dosing advice when AKI is present.

UNITS. Serum creatinine is handled in mg/dL internally. Use `umol_to_mgdl()` if
your source reports micromol/L (UK labs typically do; MIMIC reports mg/dL).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional, Sequence

# --------------------------------------------------------------------------
# Unit helpers
# --------------------------------------------------------------------------
UMOL_PER_MGDL = 88.4


def umol_to_mgdl(scr_umol_l: float) -> float:
    """Convert serum creatinine micromol/L -> mg/dL (UK labs -> equation units)."""
    return scr_umol_l / UMOL_PER_MGDL


def mgdl_to_umol(scr_mgdl: float) -> float:
    return scr_mgdl * UMOL_PER_MGDL


def _is_female(sex: str) -> bool:
    return str(sex).strip().upper().startswith("F")


# --------------------------------------------------------------------------
# 1. eGFR — CKD-EPI 2021 (race-free)
# --------------------------------------------------------------------------
def egfr_ckd_epi_2021(scr_mgdl: float, age: float, sex: str) -> Optional[float]:
    """Race-free CKD-EPI 2021 eGFR in mL/min/1.73m^2.

        eGFR = 142 x min(Scr/k,1)^a x max(Scr/k,1)^-1.200 x 0.9938^age x 1.012[F]
        k = 0.7 (female) / 0.9 (male);  a = -0.241 (female) / -0.302 (male)

    Validated for adults; returns None on non-positive creatinine.
    """
    if scr_mgdl is None or scr_mgdl <= 0 or age is None:
        return None
    female = _is_female(sex)
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    ratio = scr_mgdl / k
    egfr = (142.0
            * (min(ratio, 1.0) ** a)
            * (max(ratio, 1.0) ** -1.200)
            * (0.9938 ** age))
    if female:
        egfr *= 1.012
    return round(egfr, 1)


# --------------------------------------------------------------------------
# 2. CrCl — Cockcroft-Gault
# --------------------------------------------------------------------------
def cockcroft_gault(scr_mgdl: float, age: float, sex: str,
                    weight_kg: Optional[float]) -> Optional[float]:
    """Cockcroft-Gault creatinine clearance in mL/min (NOT BSA-normalised).

        CrCl = [(140 - age) x weight(kg) x 0.85 if female] / (72 x Scr mg/dL)

    Returns None when weight is unavailable — the caller must then fall back to
    eGFR and flag that the value is an approximation for CrCl-dosed drugs.
    """
    if not weight_kg or scr_mgdl is None or scr_mgdl <= 0 or age is None:
        return None
    factor = 0.85 if _is_female(sex) else 1.0
    crcl = ((140.0 - age) * weight_kg * factor) / (72.0 * scr_mgdl)
    return round(crcl, 1)


def ideal_body_weight(height_cm: float, sex: str) -> Optional[float]:
    """Devine ideal body weight (kg) — an alternative weight basis for CrCl.

    Actual body weight overestimates CrCl in obesity; document whichever basis
    you use. Devine: 50 kg (male) / 45.5 kg (female) + 2.3 kg per inch over 5ft.
    """
    if not height_cm:
        return None
    inches_over_5ft = (height_cm / 2.54) - 60.0
    base = 45.5 if _is_female(sex) else 50.0
    return round(max(base + 2.3 * inches_over_5ft, base * 0.6), 1)


# --------------------------------------------------------------------------
# 3. AKI — KDIGO staging (serum-creatinine route)
# --------------------------------------------------------------------------
# KDIGO serum-creatinine criteria:
#   Stage 1: >=0.3 mg/dL rise within 48h  OR  1.5-1.9 x baseline within 7 days
#   Stage 2: 2.0-2.9 x baseline
#   Stage 3: >=3.0 x baseline  OR  Scr >=4.0 mg/dL  OR  initiation of RRT
# The urine-output criterion (<0.5 mL/kg/h for 6h) requires the MIMIC-IV ICU
# module (outputevents) and is NOT implemented here — state as a limitation.

AKI_ABSOLUTE_RISE = 0.3       # mg/dL within 48h
AKI_STAGE3_ABSOLUTE = 4.0     # mg/dL
BASELINE_WINDOW_DAYS = 7
ACUTE_WINDOW_DAYS = 2


def _as_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.fromisoformat(str(d)[:10]).date()


def aki_stage_for_point(measured_on, scr_mgdl: float,
                        history: Sequence[tuple]) -> int:
    """KDIGO AKI stage (0-3) for one creatinine reading.

    `history` is an iterable of (date, scr_mgdl) for the SAME patient, any order;
    only readings strictly before `measured_on` are used.

    Baseline = the lowest creatinine in the preceding 7 days (the standard
    operational proxy when a true outpatient baseline is unknown).
    """
    if scr_mgdl is None or scr_mgdl <= 0:
        return 0
    today = _as_date(measured_on)

    prior = [(_as_date(d), float(s)) for d, s in history
             if s is not None and float(s) > 0 and _as_date(d) < today]
    if not prior:
        # No history: only the absolute stage-3 threshold can be applied.
        return 3 if scr_mgdl >= AKI_STAGE3_ABSOLUTE else 0

    within_7d = [s for d, s in prior if (today - d).days <= BASELINE_WINDOW_DAYS]
    within_48h = [s for d, s in prior if (today - d).days <= ACUTE_WINDOW_DAYS]

    baseline = min(within_7d) if within_7d else min(s for _, s in prior)
    ratio = scr_mgdl / baseline if baseline > 0 else 0.0

    # Stage 3
    if ratio >= 3.0 or scr_mgdl >= AKI_STAGE3_ABSOLUTE:
        return 3
    # Stage 2
    if ratio >= 2.0:
        return 2
    # Stage 1 — relative rise, or absolute rise within 48h
    if ratio >= 1.5:
        return 1
    if within_48h and (scr_mgdl - min(within_48h)) >= AKI_ABSOLUTE_RISE:
        return 1
    return 0


def aki_stages_for_series(series: Sequence[tuple]) -> list[int]:
    """Stage every reading in a patient's series of (date, scr_mgdl)."""
    ordered = sorted(series, key=lambda t: _as_date(t[0]))
    out = []
    for i, (d, s) in enumerate(ordered):
        out.append(aki_stage_for_point(d, s, ordered[:i]))
    return out


AKI_LABELS = {0: "none", 1: "stage 1", 2: "stage 2", 3: "stage 3"}


# --------------------------------------------------------------------------
# 4. CKD — KDIGO GFR category
# --------------------------------------------------------------------------
# G1  >=90    normal/high        G3b 30-44   moderate-severe
# G2  60-89   mildly decreased   G4  15-29   severely decreased
# G3a 45-59   mild-moderate      G5  <15     kidney failure
CKD_BANDS = [
    (90, float("inf"), "G1"), (60, 90, "G2"), (45, 60, "G3a"),
    (30, 45, "G3b"), (15, 30, "G4"), (0, 15, "G5"),
]
CKD_CHRONICITY_DAYS = 90


def ckd_stage(egfr: Optional[float]) -> Optional[str]:
    """KDIGO GFR category (G1..G5) for a single eGFR — point-in-time only."""
    if egfr is None:
        return None
    for lo, hi, label in CKD_BANDS:
        if lo <= egfr < hi:
            return label
    return None


def ckd_confirmed(series: Iterable[tuple], threshold: float = 60.0,
                  min_days: int = CKD_CHRONICITY_DAYS) -> bool:
    """Does the patient meet KDIGO's CHRONICITY requirement?

    True when eGFR stays below `threshold` across readings spanning at least
    `min_days` (default 90). This is what separates true CKD from a transient
    dip; a point-in-time G-category alone does NOT establish CKD.
    """
    pts = sorted(((_as_date(d), e) for d, e in series if e is not None),
                 key=lambda t: t[0])
    low = [(d, e) for d, e in pts if e < threshold]
    if len(low) < 2:
        return False
    return (low[-1][0] - low[0][0]).days >= min_days


def egfr_reliable(aki_stage_value: int) -> bool:
    """eGFR/CrCl assume steady state — unreliable once AKI is present."""
    return (aki_stage_value or 0) == 0
