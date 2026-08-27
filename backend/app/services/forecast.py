"""
Time-to-breach forecasting — the "anticipation" component.

Given a patient's eGFR trajectory, fit a linear trend and project it forward with
a prediction interval (an uncertainty cone that widens into the future). Then solve
for WHEN the projection crosses the next critical renal threshold — a predicted
"time to breach", with an optimistic/pessimistic range from the interval bounds.

This turns the static risk score into a countdown, which is the literal meaning of
"anticipation" in the project's thesis.

Method: ordinary least squares on (years, eGFR). Prediction interval uses the
standard OLS formula, so the cone widens with distance from the observed data —
honest uncertainty, not a flat guess. Requires >= 3 readings.

Evaluation: `backtest()` holds out each patient's last reading, forecasts it from
the earlier ones, and reports mean absolute error — so the component is measured,
not just asserted.
"""
from __future__ import annotations
from datetime import date, timedelta
import numpy as np

# critical renal thresholds (eGFR mL/min/1.73m2), worst first
THRESHOLDS = [15, 30, 45]        # G5 boundary, G4 boundary, G3b boundary
HORIZON_DAYS = 240               # how far to project the cone


# t-values for 95% prediction interval, small-sample (df -> t). Falls back to 1.96.
_T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36,
        8: 2.31, 9: 2.26, 10: 2.23, 15: 2.13, 20: 2.09, 30: 2.04}

def _t95(df: int) -> float:
    if df in _T95:
        return _T95[df]
    if df <= 0:
        return 12.71
    keys = sorted(_T95)
    for k in keys:
        if df <= k:
            return _T95[k]
    return 1.96


def _as_date(d):
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def forecast_patient(series, thresholds=THRESHOLDS, horizon_days=HORIZON_DAYS):
    """series: list of (date, egfr). Returns a forecast dict or {'ok': False}."""
    pts = sorted(((_as_date(d), float(e)) for d, e in series if e is not None),
                 key=lambda t: t[0])
    if len(pts) < 3:
        return {"ok": False, "reason": "need >= 3 readings to forecast"}

    t0 = pts[0][0]
    x = np.array([(d - t0).days / 365.25 for d, _ in pts])
    y = np.array([e for _, e in pts])
    n = len(x)

    # OLS fit
    b, a = np.polyfit(x, y, 1)              # slope, intercept
    yhat = a + b * x
    sse = float(np.sum((y - yhat) ** 2))
    s = np.sqrt(sse / (n - 2)) if n > 2 else 0.0
    xbar = x.mean()
    sxx = float(np.sum((x - xbar) ** 2)) or 1e-9
    tval = _t95(n - 2)
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
    r2 = 1 - sse / ss_tot

    def band(xq):
        se = s * np.sqrt(1 + 1 / n + (xq - xbar) ** 2 / sxx)
        c = a + b * xq
        return c, c - tval * se, c + tval * se

    # project the cone forward
    last_date = pts[-1][0]
    forecast = []
    for dd in range(0, horizon_days + 1, 10):
        xq = ((last_date - t0).days + dd) / 365.25
        c, lo, hi = band(xq)
        forecast.append({
            "date": (last_date + timedelta(days=dd)).isoformat(),
            "egfr": round(float(c), 1),
            "lower": round(float(max(lo, 0)), 1),
            "upper": round(float(hi), 1),
        })

    # time-to-breach: next threshold strictly below the latest eGFR
    latest = y[-1]
    target = next((th for th in sorted(thresholds) if th < latest), None)
    breach = {"projected": False}
    if target is not None and b < 0:
        # central crossing: a + b*x = target
        x_cross = (target - a) / b
        days_c = x_cross * 365.25 - (last_date - t0).days
        if days_c > 0:
            # range from the cone: lower bound hits sooner, upper later
            def cross_days(which):
                # solve band(xq)=target numerically over horizon
                for dd in range(0, 366 * 3, 5):
                    xq = ((last_date - t0).days + dd) / 365.25
                    c, lo, hi = band(xq)
                    v = {"c": c, "lo": lo, "hi": hi}[which]
                    if v <= target:
                        return dd
                return None
            d_lo = cross_days("lo")     # pessimistic (soonest)
            d_hi = cross_days("hi")     # optimistic (latest)
            breach = {
                "projected": True, "threshold": target,
                "days": int(round(days_c)),
                "date": (last_date + timedelta(days=int(round(days_c)))).isoformat(),
                "range_days": [d_lo, d_hi],
                "range_dates": [
                    (last_date + timedelta(days=d_lo)).isoformat() if d_lo is not None else None,
                    (last_date + timedelta(days=d_hi)).isoformat() if d_hi is not None else None,
                ],
            }

    return {
        "ok": True,
        "history": [{"date": d.isoformat(), "egfr": round(e, 1)} for d, e in pts],
        "forecast": forecast,
        "slope_per_year": round(float(b), 2),
        "r2": round(float(r2), 3),
        "thresholds": thresholds,
        "next_threshold": target,
        "breach": breach,
    }


def backtest(patient_series_list):
    """Hold out each patient's LAST reading, forecast it from the earlier ones,
    report mean absolute error. patient_series_list: list of [(date, egfr), ...]."""
    errs = []
    for series in patient_series_list:
        pts = sorted(((_as_date(d), float(e)) for d, e in series if e is not None),
                     key=lambda t: t[0])
        if len(pts) < 4:
            continue
        train, (hd, hy) = pts[:-1], pts[-1]
        f = forecast_patient(train, horizon_days=(hd - train[-1][0]).days + 1)
        if not f["ok"]:
            continue
        # predicted eGFR at the held-out date = central line extrapolated
        t0 = train[0][0]
        x = np.array([(d - t0).days / 365.25 for d, _ in train])
        y = np.array([e for _, e in train])
        b, a = np.polyfit(x, y, 1)
        pred = a + b * ((hd - t0).days / 365.25)
        errs.append(abs(pred - hy))
    if not errs:
        return {"n": 0}
    return {"n": len(errs), "mae": round(float(np.mean(errs)), 2),
            "median_ae": round(float(np.median(errs)), 2)}
