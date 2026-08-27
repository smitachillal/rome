"""
Drug-drug interaction service — severity-graded, DDInter-style.

Two data sources, checked in order:
  1. A loaded DDInter dataset (interactions.db table), if you've run the loader.
  2. A built-in curated set of renal-relevant pairs (works out of the box).

Returns interactions graded Major / Moderate / Minor / Unknown — the same
grading DDInter uses — with interaction + management text, ready to render as a
network graph and detail cards.

SAFETY: "no interaction found" means none in THIS source, never "safe". DDInter's
own terms note that absence from the database does not prove no interaction exists.
"""
from __future__ import annotations
import os, sqlite3
from itertools import combinations

# curated renal-relevant interactions (works with no download).
# (drugA_set, drugB_set, severity, interaction_text, management_text)
CURATED = [
    ({"apixaban","rivaroxaban","dabigatran","enoxaparin","warfarin"},
     {"apixaban","rivaroxaban","dabigatran","enoxaparin","warfarin"},
     "Major",
     "Concomitant use of two agents that alter haemostasis increases the risk of bleeding, including major and potentially fatal haemorrhage.",
     "Avoid combining anticoagulants unless specifically indicated. If unavoidable, monitor closely for bleeding and review the indication."),
    ({"ramipril","lisinopril","enalapril"}, {"spironolactone"},
     "Major",
     "ACE inhibitor with a potassium-sparing diuretic can cause severe hyperkalaemia, especially in renal impairment.",
     "Monitor serum potassium and renal function closely; avoid in advanced CKD or use with careful monitoring."),
    ({"digoxin"}, {"spironolactone"},
     "Moderate",
     "Spironolactone can increase plasma digoxin concentration and may interfere with some digoxin assays.",
     "Monitor digoxin levels and for signs of toxicity; adjust dose as needed."),
    ({"gentamicin","vancomycin"}, {"ramipril","lisinopril","enalapril"},
     "Moderate",
     "Additive nephrotoxicity: a nephrotoxic antibiotic combined with an ACE inhibitor increases the risk of renal deterioration.",
     "Monitor renal function frequently; ensure adequate hydration; review the need for both agents."),
    ({"gentamicin"}, {"vancomycin"},
     "Major",
     "Two nephrotoxic (and ototoxic) agents together substantially increase the risk of acute kidney injury and hearing loss.",
     "Avoid combination where possible; if required, monitor drug levels, renal function and audiometry."),
    ({"apixaban","rivaroxaban","dabigatran","enoxaparin"}, {"gentamicin"},
     "Minor",
     "Aminoglycoside-induced changes in renal function may alter anticoagulant clearance.",
     "Monitor renal function; watch for altered anticoagulant effect."),
    ({"metformin"}, {"ramipril","lisinopril","enalapril"},
     "Minor",
     "ACE inhibitors may enhance the blood-glucose-lowering effect; relevant mainly if renal function changes abruptly.",
     "Monitor blood glucose and renal function, particularly during acute illness."),
]

SEVERITY_ORDER = {"Major": 0, "Moderate": 1, "Minor": 2, "Unknown": 3}
DB_PATH = os.getenv("INTERACTIONS_DB", "interactions.db")


def _from_ddinter(a: str, b: str):
    """Look up a pair in a loaded DDInter table, if present."""
    if not os.path.exists(DB_PATH):
        return None
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        row = cur.execute(
            "SELECT severity, interaction, management FROM ddinter "
            "WHERE (drug_a=? AND drug_b=?) OR (drug_a=? AND drug_b=?) LIMIT 1",
            (a, b, b, a)).fetchone()
        con.close()
        if row:
            return {"severity": row[0], "interaction": row[1], "management": row[2],
                    "source": "DDInter"}
    except Exception:
        return None
    return None


def _from_curated(a: str, b: str):
    for sa, sb, sev, inter, mgmt in CURATED:
        if (a in sa and b in sb) or (a in sb and b in sa):
            return {"severity": sev, "interaction": inter, "management": mgmt,
                    "source": "Curated (renal)"}
    return None


def check_pair(a: str, b: str) -> dict:
    a, b = a.lower().strip(), b.lower().strip()
    hit = _from_ddinter(a, b) or _from_curated(a, b)
    if hit is None:
        return {"drug_a": a, "drug_b": b, "severity": "Unknown",
                "interaction": None, "management": None, "source": None}
    return {"drug_a": a, "drug_b": b, **hit}


def check_all(drugs: list[str]) -> dict:
    """Check every pair among the drugs. Returns nodes, edges, and detail cards
    shaped for a network graph + cards (DDInter-style)."""
    uniq = sorted(set(d.lower().strip() for d in drugs if d))
    pairs = []
    counts = {"Major": 0, "Moderate": 0, "Minor": 0, "Unknown": 0}
    for a, b in combinations(uniq, 2):
        r = check_pair(a, b)
        pairs.append(r)
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1

    pairs.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
    # graph nodes/edges (edges only where an interaction is known or unknown-but-checked)
    nodes = [{"id": d, "label": d.capitalize()} for d in uniq]
    edges = [{"source": r["drug_a"], "target": r["drug_b"],
              "severity": r["severity"]} for r in pairs]
    return {"nodes": nodes, "edges": edges, "pairs": pairs, "counts": counts,
            "n_drugs": len(uniq)}
