"""
Potassium rule layer — hyperkalaemia AND hypokalaemia.

Deterministic thresholds and drug attribution. As with the renal rule layer, this
is authoritative reference logic: the ML model ranks risk, these rules decide what
counts as a breach and which agents could be responsible.

THRESHOLDS (serum potassium, mmol/L). Normal range ~3.5-5.0.
    >= 6.0  severe hyperkalaemia   -> URGENT: arrhythmia risk, immediate action
    >= 5.5  hyperkalaemia          -> action required
    >= 5.0  high-normal            -> monitor
    3.5-5.0 normal
    <  3.5  hypokalaemia           -> action required
    <  3.0  severe hypokalaemia    -> URGENT: arrhythmia risk

Both extremes cause cardiac arrhythmia, which is why the supervisor asked for both.
"""
from __future__ import annotations

# ---- thresholds ----
K_SEVERE_HIGH = 6.0
K_HIGH = 5.5
K_HIGH_NORMAL = 5.0
K_LOW = 3.5
K_SEVERE_LOW = 3.0

FLAG_SEVERE_HIGH = "severe_hyperkalaemia"
FLAG_HIGH = "hyperkalaemia"
FLAG_HIGH_NORMAL = "high_normal"
FLAG_NORMAL = "normal"
FLAG_LOW = "hypokalaemia"
FLAG_SEVERE_LOW = "severe_hypokalaemia"

FLAG_LABELS = {
    FLAG_SEVERE_HIGH: ("SEVERE HIGH", "urgent", "K+ >= 6.0 — urgent action; arrhythmia risk"),
    FLAG_HIGH: ("HIGH", "urgent", "K+ >= 5.5 — action required"),
    FLAG_HIGH_NORMAL: ("HIGH-NORMAL", "review", "K+ >= 5.0 — monitor"),
    FLAG_NORMAL: ("NORMAL", "ok", "K+ within 3.5-5.0"),
    FLAG_LOW: ("LOW", "urgent", "K+ < 3.5 — action required"),
    FLAG_SEVERE_LOW: ("SEVERE LOW", "urgent", "K+ < 3.0 — urgent action; arrhythmia risk"),
}


def classify_k(k: float | None) -> str | None:
    """Map a serum potassium value to its clinical band."""
    if k is None:
        return None
    if k >= K_SEVERE_HIGH:
        return FLAG_SEVERE_HIGH
    if k >= K_HIGH:
        return FLAG_HIGH
    if k >= K_HIGH_NORMAL:
        return FLAG_HIGH_NORMAL
    if k < K_SEVERE_LOW:
        return FLAG_SEVERE_LOW
    if k < K_LOW:
        return FLAG_LOW
    return FLAG_NORMAL


def is_breach(k: float | None) -> bool:
    """Did this reading breach either action threshold (>=5.5 or <3.5)?"""
    if k is None:
        return False
    return k >= K_HIGH or k < K_LOW


# ---------------------------------------------------------------------------
# Drug catalogue — agents that RAISE or LOWER serum potassium.
#   direction: +1 raises K+, -1 lowers K+
#   weight   : rough relative contribution (1 = modest, 3 = strong)
# Weights are for attribution/ranking only, not dosing. Verify against BNF.
# ---------------------------------------------------------------------------
K_DRUGS = {
    # --- RAISE potassium (hyperkalaemia risk) ---
    "ramipril":        (+1, 2, "ACE inhibitor"),
    "lisinopril":      (+1, 2, "ACE inhibitor"),
    "enalapril":       (+1, 2, "ACE inhibitor"),
    "perindopril":     (+1, 2, "ACE inhibitor"),
    "candesartan":     (+1, 2, "ARB"),
    "losartan":        (+1, 2, "ARB"),
    "valsartan":       (+1, 2, "ARB"),
    "irbesartan":      (+1, 2, "ARB"),
    "spironolactone":  (+1, 3, "potassium-sparing diuretic (MRA)"),
    "eplerenone":      (+1, 3, "potassium-sparing diuretic (MRA)"),
    "amiloride":       (+1, 3, "potassium-sparing diuretic"),
    "triamterene":     (+1, 3, "potassium-sparing diuretic"),
    "trimethoprim":    (+1, 2, "antibacterial — blocks renal K+ excretion"),
    "co-trimoxazole":  (+1, 2, "antibacterial — blocks renal K+ excretion"),
    "heparin":         (+1, 1, "suppresses aldosterone"),
    "enoxaparin":      (+1, 1, "LMWH — suppresses aldosterone"),
    "ibuprofen":       (+1, 1, "NSAID — reduces renal perfusion"),
    "naproxen":        (+1, 1, "NSAID — reduces renal perfusion"),
    "ciclosporin":     (+1, 2, "calcineurin inhibitor"),
    "tacrolimus":      (+1, 2, "calcineurin inhibitor"),
    "potassium chloride": (+1, 3, "potassium supplement"),
    "sacubitril":      (+1, 2, "ARNI"),
    # --- LOWER potassium (hypokalaemia risk) ---
    "furosemide":      (-1, 3, "loop diuretic"),
    "bumetanide":      (-1, 3, "loop diuretic"),
    "torasemide":      (-1, 3, "loop diuretic"),
    "bendroflumethiazide": (-1, 2, "thiazide diuretic"),
    "indapamide":      (-1, 2, "thiazide-like diuretic"),
    "hydrochlorothiazide": (-1, 2, "thiazide diuretic"),
    "metolazone":      (-1, 3, "thiazide-like diuretic"),
    "salbutamol":      (-1, 2, "beta-2 agonist — shifts K+ intracellularly"),
    "insulin":         (-1, 2, "shifts K+ intracellularly"),
    "prednisolone":    (-1, 1, "corticosteroid — mineralocorticoid effect"),
    "hydrocortisone":  (-1, 1, "corticosteroid"),
    "amphotericin":    (-1, 3, "renal K+ wasting"),
    "theophylline":    (-1, 1, "shifts K+ intracellularly"),
}

RAISING = {d for d, (dirn, _, _) in K_DRUGS.items() if dirn > 0}
LOWERING = {d for d, (dirn, _, _) in K_DRUGS.items() if dirn < 0}


def k_agents(drugs: list[str]) -> dict:
    """Identify every potassium-affecting agent in a regimen, with direction."""
    raising, lowering = [], []
    for d in {str(x).lower().strip() for x in drugs}:
        hit = K_DRUGS.get(d)
        if hit is None:                      # tolerate 'ramipril 2.5mg' style names
            hit = next((K_DRUGS[k] for k in K_DRUGS if k in d), None)
            if hit is None:
                continue
            d = next(k for k in K_DRUGS if k in d)
        dirn, weight, cls = hit
        entry = {"drug": d, "class": cls, "weight": weight}
        (raising if dirn > 0 else lowering).append(entry)
    raising.sort(key=lambda x: -x["weight"])
    lowering.sort(key=lambda x: -x["weight"])
    return {
        "raising": raising, "lowering": lowering,
        "n_raising": len(raising), "n_lowering": len(lowering),
        "raising_burden": sum(x["weight"] for x in raising),
        "lowering_burden": sum(x["weight"] for x in lowering),
    }


def rule_assessment(k: float | None, drugs: list[str], egfr: float | None = None) -> dict:
    """Deterministic rule-layer verdict: band, urgency, and likely contributing agents."""
    flag = classify_k(k)
    agents = k_agents(drugs)
    label, severity, detail = FLAG_LABELS.get(flag, ("UNKNOWN", "", "No potassium reading"))

    actions = []
    if flag in (FLAG_SEVERE_HIGH, FLAG_HIGH):
        if agents["raising"]:
            names = ", ".join(a["drug"] for a in agents["raising"])
            actions.append(f"Review potassium-raising agents: {names}")
        if egfr is not None and egfr < 30:
            actions.append("eGFR < 30 — reduced renal K+ excretion compounds the risk")
        if flag == FLAG_SEVERE_HIGH:
            actions.append("URGENT: ECG and immediate clinical review")
    elif flag in (FLAG_SEVERE_LOW, FLAG_LOW):
        if agents["lowering"]:
            names = ", ".join(a["drug"] for a in agents["lowering"])
            actions.append(f"Review potassium-lowering agents: {names}")
        if flag == FLAG_SEVERE_LOW:
            actions.append("URGENT: ECG and immediate clinical review")
    elif flag == FLAG_HIGH_NORMAL and agents["n_raising"] >= 2:
        actions.append(f"{agents['n_raising']} potassium-raising agents together — "
                       "recheck potassium before adding another")

    return {"potassium": k, "flag": flag, "label": label, "severity": severity,
            "detail": detail, "agents": agents, "actions": actions}

# ---------------------------------------------------------------------------
# Medicine suggestions — what to DO about the potassium, drug by drug.
#
# Clinical principle: for hyperkalaemia you REDUCE/REVIEW the raising agents;
# you do not "add a lowering drug" to balance it. For hypokalaemia you review the
# lowering agents (and replace potassium where indicated). Alternatives below are
# switch options a pharmacist would consider — advisory only, confirm against BNF.
# ---------------------------------------------------------------------------
ALTERNATIVES = {
    "spironolactone": "if for heart failure, review dose or interval; specialist advice before stopping",
    "eplerenone":     "review dose; specialist advice before stopping in heart failure",
    "amiloride":      "usually stoppable — review whether still needed",
    "triamterene":    "usually stoppable — review whether still needed",
    "ramipril":       "consider dose reduction; do not stop abruptly in heart failure without review",
    "lisinopril":     "consider dose reduction; review indication",
    "enalapril":      "consider dose reduction; review indication",
    "perindopril":    "consider dose reduction; review indication",
    "candesartan":    "consider dose reduction; avoid combining ACEi + ARB",
    "losartan":       "consider dose reduction; avoid combining ACEi + ARB",
    "valsartan":      "consider dose reduction; avoid combining ACEi + ARB",
    "irbesartan":     "consider dose reduction; avoid combining ACEi + ARB",
    "trimethoprim":   "short course — consider an alternative antibacterial if K+ high",
    "co-trimoxazole": "consider an alternative antibacterial if K+ high",
    "ibuprofen":      "NSAIDs best avoided in CKD — consider paracetamol",
    "naproxen":       "NSAIDs best avoided in CKD — consider paracetamol",
    "potassium chloride": "review whether supplementation is still required — usually stop first",
    "heparin":        "usually continue; monitor K+",
    "enoxaparin":     "usually continue; monitor K+",
    "furosemide":     "review dose; consider potassium-sparing strategy or supplementation",
    "bumetanide":     "review dose; monitor K+",
    "bendroflumethiazide": "review dose; thiazides commonly cause hypokalaemia",
    "indapamide":     "review dose; monitor K+",
    "hydrochlorothiazide": "review dose; monitor K+",
    "metolazone":     "potent — review dose and monitor K+ closely",
    "salbutamol":     "transient effect; usually no change needed",
    "insulin":        "expected transient effect; monitor",
    "amphotericin":   "monitor K+ and magnesium closely; replace as needed",
}


def suggest_medicines(k: float | None, drugs: list[str], egfr: float | None = None) -> list[dict]:
    """Ranked, drug-level suggestions for the pharmacist.

    Returns the agents to review FIRST (highest attribution weight), the direction
    of their effect, and what a pharmacist would typically consider. Ordering is
    by contribution weight, so the output names the likely culprit rather than
    just the risk.
    """
    flag = classify_k(k)
    agents = k_agents(drugs)
    out = []

    if flag in (FLAG_SEVERE_HIGH, FLAG_HIGH, FLAG_HIGH_NORMAL):
        targets, direction = agents["raising"], "raises K+"
    elif flag in (FLAG_SEVERE_LOW, FLAG_LOW):
        targets, direction = agents["lowering"], "lowers K+"
    else:
        return []       # potassium normal: no drug change indicated

    urgent = flag in (FLAG_SEVERE_HIGH, FLAG_SEVERE_LOW)
    for rank, a in enumerate(targets, start=1):
        priority = "review first" if rank == 1 else ("review" if rank == 2 else "consider")
        out.append({
            "drug": a["drug"],
            "drug_class": a["class"],
            "effect": direction,
            "contribution": a["weight"],
            "priority": priority,
            "suggestion": ALTERNATIVES.get(a["drug"], "review indication and dose"),
            "urgent": urgent and rank == 1,
        })

    # renal context matters for hyperkalaemia specifically
    if flag in (FLAG_SEVERE_HIGH, FLAG_HIGH) and egfr is not None and egfr < 30:
        out.append({
            "drug": "(renal function)", "drug_class": "context",
            "effect": "reduced K+ excretion", "contribution": 3,
            "priority": "context", "urgent": False,
            "suggestion": f"eGFR {egfr:g} — impaired potassium excretion compounds every "
                          "raising agent above; recheck K+ sooner",
        })
    return out
