"""
Handbook safety filter — the "rules dispose" half of the system.

Given a drug and a patient's eGFR, it returns the renal-safety verdict
(normal / caution / avoid), the dose guidance, and a citation — read from the
Renal Drug Handbook dataset. This is authoritative reference logic, NOT learned:
the ML model proposes candidates, this filter decides whether each is safe.

Robustness note. The handbook's free-text dose column mixes GFR bands with dose
amounts (e.g. "3-5 mg/kg"), which naive parsing misreads as bands. We therefore
anchor ONLY on the three standard KDIGO-style bands the handbook uses almost
universally — 20-50, 10-20, <10 — and read the action segment after each. eGFR
above 50 is treated as normal renal function. A per-drug hard avoid-threshold
(from clinical knowledge) is applied as a safety backstop.
"""
from __future__ import annotations
import json, re
import pandas as pd

# hard renal avoid thresholds (eGFR mL/min) — safety backstop independent of text
AVOID_BELOW = {
    "metformin": 30, "nitrofurantoin": 45, "dabigatran": 30, "spironolactone": 30,
    "apixaban": 15, "rivaroxaban": 15, "enoxaparin": 15, "sitagliptin": 15,
    "ramipril": 15, "lisinopril": 15, "enalapril": 15,
}
# curated drug -> handbook Drug_name
HANDBOOK_NAME = {
    "metformin":"Metformin hydrochloride","sitagliptin":"Sitagliptin","ramipril":"Ramipril",
    "lisinopril":"Lisinopril","enalapril":"Enalapril maleate","apixaban":"Apixaban",
    "rivaroxaban":"Rivaroxaban","dabigatran":"Dabigatran etexilate","enoxaparin":"Enoxaparin sodium",
    "digoxin":"Digoxin","gabapentin":"Gabapentin","pregabalin":"Pregabalin","gentamicin":"Gentamicin",
    "nitrofurantoin":"Nitrofurantoin","vancomycin":"Vancomycin","allopurinol":"Allopurinol",
    "spironolactone":"Spironolactone",
}
NORMAL_ABOVE = 50           # eGFR >= 50 -> normal renal function band


def _standard_band_action(text: str, band: str) -> str | None:
    """Read the action following one of the three standard bands (20-50/10-20/<10)."""
    if not isinstance(text, str):
        return None
    t = text.replace("–", "-").replace("’", "'")
    # accept the near-standard variants the handbook uses for each conceptual band
    marks = {
        "20-50":   r"(?:20|25|30)\s*-\s*(?:50|59|60)",
        "10-20":   r"(?:10|15)\s*-\s*(?:20|29|30|45)",
        "under10": r"<\s*(?:10|15)",
    }
    order = ["20-50", "10-20", "under10"]
    pos, mend = {}, {}
    for k in order:
        m = re.search(marks[k], t)
        pos[k] = m.start() if m else None
        mend[k] = m.end() if m else None
    if pos[band] is None:
        return None
    start = mend[band]
    end = len(t)
    for k in order[order.index(band) + 1:]:
        if pos[k] is not None and pos[k] > start:
            end = pos[k]; break
    return t[start:end].strip(" .:-")[:160] or None


def _classify(action: str | None) -> str:
    if not action:
        return "unknown"
    a = action.lower()
    if re.search(r"\bavoid\b|contraindicat|not recommended|do not use", a): return "avoid"
    if re.search(r"dose as in normal|normal renal function|unchanged", a):   return "normal"
    if re.search(r"reduce|caution|monitor|titrate|%|small dose|lower|half|alternate", a): return "caution"
    return "caution"


class HandbookSafety:
    def __init__(self, handbook_csv: str):
        df = pd.read_csv(handbook_csv)
        self.by_name = {r["Drug_name"]: r for _, r in df.iterrows()}

    def _row(self, drug: str):
        hb = HANDBOOK_NAME.get(drug, drug)
        return self.by_name.get(hb)

    def assess(self, drug: str, egfr: float) -> dict:
        """Return {status, dose, reference, band} for a drug at a patient's eGFR."""
        row = self._row(drug)
        avoid_below = AVOID_BELOW.get(drug)

        # safety backstop first
        if avoid_below is not None and egfr < avoid_below:
            status_floor = "avoid"
        else:
            status_floor = None

        dose_text, reference = "", ""
        if row is not None:
            reference = "Renal Drug Handbook (5th ed.)"
            rule_text = row.get("Dose_in_renal_impairment_GFR_mL_min", "")
            if egfr >= NORMAL_ABOVE:
                band, action = "normal (>50)", "Dose as in normal renal function"
            else:
                band = "20-50" if egfr >= 20 else ("10-20" if egfr >= 10 else "under10")
                action = _standard_band_action(rule_text, band) or ""
            status = _classify(action)
            dose_text = action or "See handbook monograph"
        else:
            band, status, dose_text = "n/a", "unknown", "Drug not in handbook subset"

        # apply the backstop: never downgrade a hard avoid
        if status_floor == "avoid":
            status = "avoid"
            if not dose_text or _classify(dose_text) != "avoid":
                dose_text = f"Avoid: eGFR {egfr:g} below {avoid_below} mL/min"

        return {"drug": drug, "status": status, "band": band,
                "dose": dose_text, "reference": reference}


if __name__ == "__main__":
    import sys
    hb = HandbookSafety("/mnt/user-data/outputs/renal_drug_handbook_decision_tree_dataset.csv")
    print("Demo — same drugs at different eGFR levels:\n")
    for egfr in (80, 40, 12):
        print(f"--- patient eGFR {egfr} ---")
        for d in ["metformin", "apixaban", "gentamicin", "nitrofurantoin", "digoxin"]:
            a = hb.assess(d, egfr)
            print(f"  {d:14s} [{a['status']:7s}] band {a['band']:11s} {a['dose'][:50]}")
        print()
