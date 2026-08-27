"""
Structured medication review — per-drug efficacy, side-effect and PK/PD assessment.

Implements the clinical requirement: "regular review of how well the medication is
controlling the condition(s), including assessment of drug efficacy, side effects,
pharmacokinetics and pharmacodynamics for the patient."

HONEST DESIGN. A review has two halves:
  * what the SYSTEM can assess from held data (renal function trend, review timing,
    PK-based accumulation context) — computed and shown with a status;
  * what needs a HUMAN (symptoms, adherence, markers not in the dataset, e.g.
    HbA1c/BP until imported) — surfaced as explicit "assess at review" prompts,
    never silently skipped or faked.

The per-drug knowledge (efficacy marker, side-effect markers, review interval) is a
curated catalogue in our own words following standard practice; PK values come from
the Renal Drug Handbook dataset already in the project.
"""
from __future__ import annotations
from datetime import date, timedelta

# drug -> review profile.
#   efficacy_marker : what shows the condition is controlled
#   side_effects    : key adverse effects to check
#   monitor_labs    : labs to watch; "renal" is auto-assessed from the DB
#   interval_days   : suggested review interval in renal impairment (conservative)
REVIEW_CATALOGUE = {
    "metformin":     dict(indication="type 2 diabetes", efficacy_marker="HbA1c (target per care plan)",
                          side_effects=["GI upset", "B12 deficiency (long-term)", "lactic acidosis risk if renal decline"],
                          monitor_labs=["renal", "HbA1c", "B12 (annual)"], interval_days=90),
    "sitagliptin":   dict(indication="type 2 diabetes", efficacy_marker="HbA1c",
                          side_effects=["GI upset", "pancreatitis (rare)"],
                          monitor_labs=["renal", "HbA1c"], interval_days=180),
    "ramipril":      dict(indication="hypertension / HF", efficacy_marker="blood pressure (and HF symptoms)",
                          side_effects=["dry cough", "hyperkalaemia", "renal deterioration", "hypotension"],
                          monitor_labs=["renal", "potassium", "BP"], interval_days=90),
    "lisinopril":    dict(indication="hypertension / HF", efficacy_marker="blood pressure",
                          side_effects=["dry cough", "hyperkalaemia", "renal deterioration"],
                          monitor_labs=["renal", "potassium", "BP"], interval_days=90),
    "enalapril":     dict(indication="heart failure", efficacy_marker="HF symptoms / BP",
                          side_effects=["hyperkalaemia", "renal deterioration", "hypotension"],
                          monitor_labs=["renal", "potassium", "BP"], interval_days=90),
    "apixaban":      dict(indication="anticoagulation (AF/VTE)", efficacy_marker="absence of thromboembolic events (no routine lab)",
                          side_effects=["bleeding", "anaemia"],
                          monitor_labs=["renal", "FBC (if bleeding suspected)"], interval_days=180),
    "rivaroxaban":   dict(indication="anticoagulation", efficacy_marker="absence of thromboembolic events",
                          side_effects=["bleeding"], monitor_labs=["renal", "FBC"], interval_days=180),
    "dabigatran":    dict(indication="anticoagulation", efficacy_marker="absence of thromboembolic events",
                          side_effects=["bleeding", "dyspepsia"], monitor_labs=["renal"], interval_days=90),
    "enoxaparin":    dict(indication="anticoagulation", efficacy_marker="clinical course; anti-Xa if monitored",
                          side_effects=["bleeding", "HIT (rare)"], monitor_labs=["renal", "platelets"], interval_days=30),
    "digoxin":       dict(indication="heart failure / AF rate", efficacy_marker="heart rate / symptom control",
                          side_effects=["toxicity: nausea, visual disturbance, arrhythmia"],
                          monitor_labs=["renal", "digoxin level", "potassium"], interval_days=90),
    "spironolactone":dict(indication="heart failure", efficacy_marker="HF symptoms / fluid status",
                          side_effects=["hyperkalaemia", "gynaecomastia", "renal deterioration"],
                          monitor_labs=["renal", "potassium"], interval_days=30),
    "gentamicin":    dict(indication="serious infection", efficacy_marker="infection markers (CRP/WCC, clinical response)",
                          side_effects=["nephrotoxicity", "ototoxicity"],
                          monitor_labs=["renal", "gentamicin level"], interval_days=2),
    "vancomycin":    dict(indication="serious infection", efficacy_marker="infection markers / clinical response",
                          side_effects=["nephrotoxicity", "red man syndrome"],
                          monitor_labs=["renal", "vancomycin trough"], interval_days=2),
    "nitrofurantoin":dict(indication="UTI", efficacy_marker="symptom resolution / urine culture",
                          side_effects=["pulmonary toxicity (long-term)", "hepatotoxicity", "neuropathy"],
                          monitor_labs=["renal"], interval_days=30),
    "allopurinol":   dict(indication="gout prevention", efficacy_marker="serum urate (and flare frequency)",
                          side_effects=["rash / hypersensitivity", "marrow suppression (rare)"],
                          monitor_labs=["renal", "urate"], interval_days=90),
    "gabapentin":    dict(indication="neuropathic pain", efficacy_marker="pain scores / function",
                          side_effects=["sedation", "dizziness", "accumulation in renal impairment"],
                          monitor_labs=["renal"], interval_days=90),
    "pregabalin":    dict(indication="neuropathic pain", efficacy_marker="pain scores / function",
                          side_effects=["sedation", "weight gain", "accumulation in renal impairment"],
                          monitor_labs=["renal"], interval_days=90),
    "lithium":       dict(indication="mood stabilisation", efficacy_marker="mental state / lithium level in range",
                          side_effects=["nephrotoxicity (long-term)", "thyroid dysfunction", "toxicity: tremor, confusion"],
                          monitor_labs=["renal", "lithium level", "TFTs"], interval_days=90),
}

AUTO_ASSESSABLE = {"renal"}      # markers the system can check from its own DB today


def _renal_status(labs):
    """Auto-assessment of the renal marker from the patient's own series."""
    pts = sorted([(l.measured_on, l.egfr) for l in labs if l.egfr is not None])
    if len(pts) < 2:
        return {"status": "insufficient data", "detail": "fewer than 2 eGFR readings"}
    latest_d, latest_e = pts[-1]
    prev_e = pts[-2][1]
    delta = latest_e - prev_e
    aki = max((l.aki_stage or 0) for l in labs)
    if aki > 0:
        return {"status": "unstable", "detail": f"AKI stage {aki} in series — eGFR unreliable for dosing"}
    if delta <= -10:
        return {"status": "deteriorating", "detail": f"eGFR fell {abs(delta):.0f} since previous reading"}
    if latest_e < 30:
        return {"status": "review dose", "detail": f"latest eGFR {latest_e:.0f} — check dose band"}
    return {"status": "stable", "detail": f"latest eGFR {latest_e:.0f}, change {delta:+.0f}"}


def _pk_context(drug, handbook_features):
    f = (handbook_features or {}).get(drug, {})
    bits = []
    if f.get("drug_half_life") is not None:
        bits.append(f"half-life ~{f['drug_half_life']:g} h (longer in renal impairment)")
    if f.get("drug_pct_excreted") is not None:
        bits.append(f"~{f['drug_pct_excreted']:g}% renally excreted")
    if f.get("drug_protein_binding") is not None:
        bits.append(f"protein binding {f['drug_protein_binding']:g}%")
    return "; ".join(bits) or "PK data: see handbook monograph"


def build_review(patient_labs, patient_drugs, handbook_features=None, today=None) -> dict:
    """Assemble the structured medication review for one patient."""
    today = today or date.today()
    latest_lab = max((l.measured_on for l in patient_labs), default=None)

    rows = []
    for d in sorted(set(x.lower() for x in patient_drugs)):
        prof = REVIEW_CATALOGUE.get(d)
        if prof is None:
            rows.append({"drug": d, "known": False})
            continue
        renal = _renal_status(patient_labs)
        # review due: interval since last lab (proxy for last review touchpoint)
        due_date = (latest_lab + timedelta(days=prof["interval_days"])) if latest_lab else None
        overdue = bool(due_date and today > due_date)
        rows.append({
            "drug": d, "known": True,
            "indication": prof["indication"],
            "efficacy_marker": prof["efficacy_marker"],
            "side_effects": prof["side_effects"],
            "monitor_labs": prof["monitor_labs"],
            "auto": {"renal": renal},                       # what the system checked itself
            "human": [m for m in prof["monitor_labs"] if m not in AUTO_ASSESSABLE],
            "pk_context": _pk_context(d, handbook_features),
            "review_interval_days": prof["interval_days"],
            "review_due": due_date.isoformat() if due_date else None,
            "overdue": overdue,
        })
    return {
        "drugs": rows,
        "note": "System-assessed items are computed from held data (renal series). "
                "Items under 'assess at review' need clinical input or data not yet "
                "captured (e.g. HbA1c, BP, symptoms, adherence).",
    }
