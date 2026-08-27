"""Deterministic rule layer.

Evaluates a patient's renal function against per-drug thresholds. Each drug is
judged on its own metric (eGFR or CrCl); level-guided drugs route to manual
review. Thresholds here are ILLUSTRATIVE and carry a source reference; in the
real system they come from the verified Renal Drug Handbook crosswalk.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RenalRule:
    ingredient: str
    metric: str            # "eGFR" | "CrCl" | "level-guided"
    review_cutoff: Optional[float]   # below this -> reduce/review
    urgent_cutoff: Optional[float]   # below this -> avoid/urgent
    action_review: str
    action_urgent: str
    reference: str


# Illustrative curated rule set (subset). VERIFY against the handbook before use.
RULES: dict[str, RenalRule] = {
    "metformin": RenalRule("metformin", "eGFR", 45, 30,
        "Reduce dose; review", "Avoid / discontinue",
        "Renal Drug Handbook 5th ed, p.640"),
    "apixaban": RenalRule("apixaban", "CrCl", 30, 15,
        "Consider dose reduction", "Not recommended",
        "Renal Drug Handbook 5th ed, p.73"),
    "rivaroxaban": RenalRule("rivaroxaban", "CrCl", 49, 15,
        "Caution; reduce for some indications", "Avoid",
        "Renal Drug Handbook 5th ed, p.891"),
    "enoxaparin": RenalRule("enoxaparin", "CrCl", 30, 15,
        "Reduce treatment dose", "Avoid / specialist",
        "Renal Drug Handbook 5th ed, p.367"),
    "gentamicin": RenalRule("gentamicin", "CrCl", 60, 30,
        "Extend interval; monitor levels", "Avoid unless essential",
        "Renal Drug Handbook 5th ed, p.479"),
    "gabapentin": RenalRule("gabapentin", "eGFR", 80, 30,
        "Reduce dose (CrCl-banded)", "Substantially reduce",
        "Renal Drug Handbook 5th ed, p.471"),
    "ramipril": RenalRule("ramipril", "eGFR", 60, 30,
        "Reduce initial dose; monitor K+", "Caution / specialist",
        "Renal Drug Handbook 5th ed, p.862"),
    "sitagliptin": RenalRule("sitagliptin", "eGFR", 45, 30,
        "Reduce dose", "Further reduce dose",
        "Renal Drug Handbook 5th ed, p.923"),
    "nitrofurantoin": RenalRule("nitrofurantoin", "eGFR", 45, 45,
        "Avoid (ineffective + toxic)", "Avoid",
        "Renal Drug Handbook 5th ed, p.717"),
    "digoxin": RenalRule("digoxin", "level-guided", None, None,
        "Reduce dose; monitor levels", "Monitor levels",
        "Renal Drug Handbook 5th ed, p.319"),
    "lithium": RenalRule("lithium", "level-guided", None, None,
        "Monitor levels & renal function", "Withhold; monitor",
        "Renal Drug Handbook 5th ed, p.598"),
    "vancomycin": RenalRule("vancomycin", "level-guided", None, None,
        "Dose by levels", "Dose by levels",
        "Renal Drug Handbook 5th ed, p.1047"),
}


def evaluate_drug(ingredient: str, egfr: float, crcl: Optional[float],
                  manual_floor: float = 60.0) -> Optional[dict]:
    """Return a flag dict for one drug, or None if the drug isn't in the rule set."""
    rule = RULES.get(ingredient.lower())
    if rule is None:
        return None

    if rule.metric == "level-guided":
        impaired = egfr < manual_floor
        return {
            "ingredient": rule.ingredient, "metric": "level-guided",
            "value_used": round(egfr, 1), "cutoff": None,
            "severity": "manual" if impaired else "none",
            "action": rule.action_review if impaired
                      else "No numeric rule; monitor per protocol",
            "reference": rule.reference,
        }

    value = crcl if (rule.metric == "CrCl" and crcl is not None) else egfr
    severity, action, cutoff = "none", "Within range", None
    if rule.urgent_cutoff is not None and value < rule.urgent_cutoff:
        severity, action, cutoff = "urgent", rule.action_urgent, rule.urgent_cutoff
    elif rule.review_cutoff is not None and value < rule.review_cutoff:
        severity, action, cutoff = "review", rule.action_review, rule.review_cutoff

    return {
        "ingredient": rule.ingredient, "metric": rule.metric,
        "value_used": round(value, 1), "cutoff": cutoff,
        "severity": severity, "action": action, "reference": rule.reference,
    }
