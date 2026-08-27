"""
Medication timeline — current vs historical, and which drugs were CONCURRENT.

Clinical rationale (supervisor feedback). Interaction analysis must consider drugs
the patient is taking TOGETHER. A drug stopped in January and one started in June
never coexisted, so flagging them as an interaction is a false alarm that erodes
trust in the tool. Every drug therefore carries a start_date and an end_date
(NULL end_date = still being taken).

Two related questions this module answers:
  * "What is the patient on RIGHT NOW?"      -> current_drugs()
  * "Did drug A and drug B ever overlap?"    -> overlaps() / concurrent_pairs()

The second is the general rule; the first is the common case. Interaction checks
run on CURRENT medicines plus any PROPOSED medicine, not the whole history.
"""
from __future__ import annotations
from datetime import date

STATUS_CURRENT = "current"
STATUS_STOPPED = "stopped"
STATUS_PLANNED = "planned"      # start date in the future
STATUS_UNKNOWN = "unknown"      # no dates recorded (legacy rows)


def reference_date(labs=None, drugs=None) -> date:
    """The 'as of' date for status decisions — the patient's own latest data point.

    WHY NOT today()? MIMIC de-identifies by shifting every date far into the future
    (years ~2100-2200). Comparing those against the real calendar date would mark
    every prescription "planned" and leave no medicine "current". Anchoring to the
    latest date in the patient's own record makes status meaningful for shifted,
    historical and live data alike.
    """
    candidates = []
    for l in (labs or []):
        d = _d(getattr(l, "measured_on", None))
        if d:
            candidates.append(d)
    for g in (drugs or []):
        for attr in ("start_date", "end_date"):
            d = _d(getattr(g, attr, None))
            if d:
                candidates.append(d)
    return max(candidates) if candidates else date.today()


def _d(v):
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def status_of(start, end, as_of: date | None = None) -> str:
    """Classify one medication at a point in time."""
    as_of = as_of or date.today()
    start, end = _d(start), _d(end)
    if start is None and end is None:
        return STATUS_UNKNOWN            # legacy row: no timeline recorded
    if start and start > as_of:
        return STATUS_PLANNED
    if end is not None and end <= as_of:
        return STATUS_STOPPED
    return STATUS_CURRENT


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    """Did two medication courses coexist at any point?

    Open-ended (NULL end) means 'still running'. Two intervals overlap when each
    starts before the other ends — the standard interval-intersection test.
    """
    a_s, a_e = _d(a_start), _d(a_end)
    b_s, b_e = _d(b_start), _d(b_end)
    # unknown timelines: fall back to assuming overlap (conservative, but flagged)
    if a_s is None and a_e is None:
        return True
    if b_s is None and b_e is None:
        return True
    a_s = a_s or date.min
    b_s = b_s or date.min
    a_e = a_e or date.max
    b_e = b_e or date.max
    return a_s <= b_e and b_s <= a_e


def summarise(drugs, as_of: date | None = None) -> list[dict]:
    """Build the medication table: one row per drug with dates and status."""
    as_of = as_of or date.today()
    rows = []
    for d in drugs:
        st = status_of(getattr(d, "start_date", None), getattr(d, "end_date", None), as_of)
        rows.append({
            "ingredient": str(d.ingredient).lower(),
            "start_date": _d(getattr(d, "start_date", None)).isoformat() if getattr(d, "start_date", None) else None,
            "end_date": _d(getattr(d, "end_date", None)).isoformat() if getattr(d, "end_date", None) else None,
            "status": st,
        })
    order = {STATUS_CURRENT: 0, STATUS_PLANNED: 1, STATUS_UNKNOWN: 2, STATUS_STOPPED: 3}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["ingredient"]))
    return rows


def current_drugs(drugs, as_of: date | None = None) -> list[str]:
    """Ingredient names the patient is taking now (plus unknown-timeline rows)."""
    return [r["ingredient"] for r in summarise(drugs, as_of)
            if r["status"] in (STATUS_CURRENT, STATUS_UNKNOWN)]


def historical_drugs(drugs, as_of: date | None = None) -> list[str]:
    return [r["ingredient"] for r in summarise(drugs, as_of)
            if r["status"] == STATUS_STOPPED]


def concurrent_pairs(drugs) -> list[tuple[str, str]]:
    """All ingredient pairs whose courses overlapped in time (any period)."""
    items = list(drugs)
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if str(a.ingredient).lower() == str(b.ingredient).lower():
                continue
            if overlaps(getattr(a, "start_date", None), getattr(a, "end_date", None),
                        getattr(b, "start_date", None), getattr(b, "end_date", None)):
                out.append((str(a.ingredient).lower(), str(b.ingredient).lower()))
    return sorted(set(tuple(sorted(p)) for p in out))

def reference_date(labs=None, drugs=None) -> date:
    """The 'as of' date for status decisions — the patient's own latest data point.

    WHY NOT today()? MIMIC de-identifies by shifting every date far into the future
    (years ~2100-2200). Comparing those against the real calendar date would mark
    every prescription "planned" and leave no medicine "current". Anchoring to the
    latest date in the patient's own record makes status meaningful for shifted,
    historical and live data alike.
    """
    candidates = []
    for l in (labs or []):
        d = _d(getattr(l, "measured_on", None))
        if d:
            candidates.append(d)
    for g in (drugs or []):
        for attr in ("start_date", "end_date"):
            d = _d(getattr(g, attr, None))
            if d:
                candidates.append(d)
    return max(candidates) if candidates else date.today()

