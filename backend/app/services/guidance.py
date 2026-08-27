"""
Role-aware UK clinical guidance layer.

Maps a patient's renal situation + the viewer's role (patient / nurse /
pharmacist / doctor) to (a) a short, plain in-app note written in general terms,
and (b) links out to the authoritative UK sources. It does NOT reproduce NICE/BNF
text — that content is licensed — it ROUTES the user to the official page.

The notes below are generic safe-practice framing in our own words, each deferring
to the official source and a qualified human. This keeps the feature copyright-safe
and clinically responsible: the tool points to guidance, it does not replace it.

Verified source URLs (checked live):
  NICE NG203 (CKD)         https://www.nice.org.uk/guidance/ng203
  NICE NG203 (public)      https://www.nice.org.uk/guidance/ng203/informationforpublic
  NICE CKS (CKD)           https://cks.nice.org.uk/topics/chronic-kidney-disease/
  SPS renal medicines      https://www.sps.nhs.uk/articles/information-resources-for-managing-medicines-in-renal-impairment/
  BNF (drugs A-Z)          https://bnf.nice.org.uk/drugs/
  NHS medicines A-Z        https://www.nhs.uk/medicines/
  NHS kidney disease       https://www.nhs.uk/conditions/kidney-disease/
  MHRA drug safety updates https://www.gov.uk/drug-safety-update
"""
from __future__ import annotations

ROLES = ["patient", "nurse", "pharmacist", "doctor"]

# BNF/NHS use predictable slugs; we build a best-effort deep link plus a safe index.
_BNF_SLUGS = {
    "metformin": "metformin-hydrochloride", "apixaban": "apixaban",
    "rivaroxaban": "rivaroxaban", "dabigatran": "dabigatran-etexilate",
    "enoxaparin": "enoxaparin-sodium", "gentamicin": "gentamicin",
    "vancomycin": "vancomycin", "digoxin": "digoxin", "ramipril": "ramipril",
    "lisinopril": "lisinopril", "enalapril": "enalapril-maleate",
    "spironolactone": "spironolactone", "allopurinol": "allopurinol",
    "gabapentin": "gabapentin", "pregabalin": "pregabalin",
    "sitagliptin": "sitagliptin", "nitrofurantoin": "nitrofurantoin",
}
_NHS_SLUGS = {
    "metformin": "metformin", "apixaban": "apixaban", "rivaroxaban": "rivaroxaban",
    "digoxin": "digoxin", "ramipril": "ramipril", "spironolactone": "spironolactone",
    "allopurinol": "allopurinol", "gabapentin": "gabapentin", "pregabalin": "pregabalin",
    "nitrofurantoin": "nitrofurantoin",
}

def bnf_link(drug: str):
    slug = _BNF_SLUGS.get(drug)
    return f"https://bnf.nice.org.uk/drugs/{slug}/" if slug else "https://bnf.nice.org.uk/drugs/"

def nhs_link(drug: str):
    slug = _NHS_SLUGS.get(drug)
    return f"https://www.nhs.uk/medicines/{slug}/" if slug else "https://www.nhs.uk/medicines/"

# role -> (short note template, list of standing resource links)
_NOTE = {
    "patient": "Your kidney function affects how some medicines are cleared from your body, "
               "so doses may need adjusting. Never stop or change a dose yourself — speak to "
               "your pharmacist or GP first. The NHS pages below explain your medicines and "
               "kidney health in plain language.",
    "nurse":   "Monitor renal function (U&Es) and fluid balance, and watch for signs of "
               "toxicity from renally-cleared drugs. Ensure eGFR/CrCl is current before dosing "
               "decisions and escalate significant changes. See the SPS and BNF resources below.",
    "pharmacist": "Verify each renally-cleared drug against BNF and the SPS renal medicines "
                  "resources at the patient's current eGFR/CrCl; check for interactions and "
                  "cumulative nephrotoxicity, and confirm against the SmPC where doses differ.",
    "doctor":  "Assess CKD stage and trajectory, review nephrotoxic and renally-cleared drugs, "
               "and consider referral/monitoring thresholds per NICE NG203. Use CKS for a "
               "practical management summary. Confirm dosing against BNF/specialist advice.",
}
_STANDING = {
    "patient": [
        ("NHS: Kidney disease", "https://www.nhs.uk/conditions/kidney-disease/"),
        ("NHS: Medicines A-Z", "https://www.nhs.uk/medicines/"),
        ("NICE CKD (information for the public)", "https://www.nice.org.uk/guidance/ng203/informationforpublic"),
    ],
    "nurse": [
        ("SPS: Managing medicines in renal impairment", "https://www.sps.nhs.uk/articles/information-resources-for-managing-medicines-in-renal-impairment/"),
        ("BNF: Drugs A-Z", "https://bnf.nice.org.uk/drugs/"),
        ("NICE NG203: CKD assessment & management", "https://www.nice.org.uk/guidance/ng203"),
    ],
    "pharmacist": [
        ("SPS: Managing medicines in renal impairment", "https://www.sps.nhs.uk/articles/information-resources-for-managing-medicines-in-renal-impairment/"),
        ("BNF: Drugs A-Z", "https://bnf.nice.org.uk/drugs/"),
        ("MHRA: Drug Safety Update", "https://www.gov.uk/drug-safety-update"),
    ],
    "doctor": [
        ("NICE NG203: CKD assessment & management", "https://www.nice.org.uk/guidance/ng203"),
        ("NICE CKS: Chronic kidney disease", "https://cks.nice.org.uk/topics/chronic-kidney-disease/"),
        ("BNF: Drugs A-Z", "https://bnf.nice.org.uk/drugs/"),
    ],
}

def _ckd_note(ckd_stage):
    """A short, generic CKD-stage framing (our words, not NICE text)."""
    if not ckd_stage:
        return None
    if ckd_stage in ("G4", "G5", 4, 5):
        return ("Advanced CKD: renally-cleared drugs often need dose reduction or avoidance, "
                "and specialist/renal input may be appropriate.")
    if ckd_stage in ("G3a", "G3b", 3):
        return ("Moderate CKD: review renally-cleared drug doses and monitor renal function "
                "regularly.")
    return "Early CKD: monitor renal function and review nephrotoxic drugs periodically."


def build_guidance(patient: dict, role: str) -> dict:
    role = role if role in ROLES else "pharmacist"
    drugs = patient.get("current_drugs", []) or []

    # per-drug official links, tailored to role (patient -> NHS, clinical -> BNF)
    per_drug = []
    for d in drugs:
        d = str(d).lower()
        if role == "patient":
            per_drug.append({"drug": d, "label": f"NHS: {d}", "url": nhs_link(d)})
        else:
            per_drug.append({"drug": d, "label": f"BNF: {d}", "url": bnf_link(d)})

    notes = [_NOTE[role]]
    ck = _ckd_note(patient.get("ckd_stage_label") or patient.get("ckd_stage"))
    if ck:
        notes.append(ck)

    return {
        "role": role,
        "note": " ".join(notes),
        "resources": [{"label": l, "url": u} for l, u in _STANDING[role]],
        "drug_links": per_drug,
        "disclaimer": "Decision support only — not a substitute for professional judgement "
                      "or the official guidance. Always confirm with the linked source.",
    }
