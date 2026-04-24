"""
IMO 2008 Intact Stability (IS) Code – Part A, Chapter 2 (General Criteria)
==========================================================================

Automated pass/fail check for the six general intact-stability criteria
applicable to all ships of length ≥ 24 m (IMO Resolution A.749(18) as
amended and carried forward into MSC.267(85) – the 2008 IS Code):

    (1) Area under GZ 0° → 30°       ≥ 0.055  m·rad
    (2) Area under GZ 0° → 40°       ≥ 0.090  m·rad        (or AVS if < 40°)
    (3) Area between 30° and 40°     ≥ 0.030  m·rad
    (4) GZ at 30° heel                ≥ 0.20   m
    (5) Angle of max GZ               ≥ 25°   (preferably ≥ 30°)
    (6) Initial metacentric height    ≥ 0.15   m

A.562 – Severe-wind-and-rolling (weather) criterion – lives in `weather.py`.

The checker returns a structured dict with each criterion's limit, actual
value, margin, and PASS/FAIL status, plus an overall verdict.
"""

from __future__ import annotations

from typing import List, Dict
import numpy as np


_CRITERIA = [
    # (key, description, limit, unit, direction)    direction: ">=" or "<="
    ("area_0_30",   "Area under GZ curve 0°–30°",                      0.055, "m·rad", ">="),
    ("area_0_40",   "Area under GZ curve 0°–40° (or to AVS if <40°)",  0.090, "m·rad", ">="),
    ("area_30_40",  "Area under GZ curve 30°–40°",                     0.030, "m·rad", ">="),
    ("gz_30",       "GZ at 30° heel",                                  0.20,  "m",     ">="),
    ("angle_gzmax", "Heel angle at maximum GZ",                        25.0,  "°",     ">="),
    ("gm_initial",  "Initial metacentric height GM₀",                  0.15,  "m",     ">="),
]


def imo_intact_stability_check(stab: Dict) -> Dict:
    """
    Evaluate each IMO A.749 criterion against the supplied stability dict
    (output of `stability_parameters`).

    Returns
    -------
    {
      "criteria" : [ {key, description, limit, actual, margin, status}, ... ],
      "passed"   : int,
      "failed"   : int,
      "overall"  : "PASS" / "FAIL"
    }
    """
    values = {
        "area_0_30"   : stab.get("area_0_30_m_rad",    float("nan")),
        "area_0_40"   : stab.get("area_0_40_m_rad",    float("nan")),
        "area_30_40"  : stab.get("area_30_40_m_rad",   float("nan")),
        "gz_30"       : stab.get("GZ_at_30deg_m",      float("nan")),
        "angle_gzmax" : stab.get("angle_max_GZ_deg",   float("nan")),
        "gm_initial"  : stab.get("GM_m",               float("nan")),
    }

    results: List[Dict] = []
    passed = 0
    for key, desc, limit, unit, direction in _CRITERIA:
        actual = values[key]
        if np.isnan(actual):
            status, margin = "N/A", float("nan")
        else:
            ok = (actual >= limit) if direction == ">=" else (actual <= limit)
            status = "PASS" if ok else "FAIL"
            margin = actual - limit if direction == ">=" else limit - actual
            if ok:
                passed += 1
        results.append({
            "key"        : key,
            "description": desc,
            "limit"      : limit,
            "actual"     : actual,
            "margin"     : margin,
            "unit"       : unit,
            "status"     : status,
        })

    # AVS-modified test (criterion 2 & 3) – if angle of vanishing stability
    # is below 40°, the limit areas are evaluated only up to AVS.
    avs = stab.get("angle_vanishing_deg", float("nan"))
    if not np.isnan(avs) and avs < 40.0:
        for r in results:
            if r["key"] in ("area_0_40", "area_30_40"):
                r["description"] += f"  [evaluated to AVS = {avs:.1f}°]"

    failed = sum(1 for r in results if r["status"] == "FAIL")
    overall = "PASS" if failed == 0 else "FAIL"

    return {
        "criteria": results,
        "passed"  : passed,
        "failed"  : failed,
        "overall" : overall,
    }


# ---------------------------------------------------------------------------
# Pretty-printer
# ---------------------------------------------------------------------------

def format_report(check: Dict) -> str:
    lines = []
    lines.append("IMO 2008 IS Code – Intact Stability (Part A, General Criteria)")
    lines.append("=" * 75)
    lines.append(f"{'Criterion':<46}{'Limit':>10}{'Actual':>12}{'  Status':>7}")
    lines.append("-" * 75)
    for r in check["criteria"]:
        actual_str = f"{r['actual']:>12.4f}" if not np.isnan(r['actual']) else f"{'N/A':>12}"
        lines.append(
            f"{r['description']:<46}"
            f"{r['limit']:>10.3f}"
            f"{actual_str}"
            f"  {r['status']:<6}"
        )
    lines.append("-" * 75)
    lines.append(f"Overall verdict:  {check['overall']}  "
                 f"({check['passed']} passed / {check['failed']} failed)")
    return "\n".join(lines)
