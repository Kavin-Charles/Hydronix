"""
IMO Severe Wind and Rolling (Weather) Criterion – A.749(18) Part A 2.3
======================================================================

A simplified implementation suitable for the hackathon demonstration:

    P (wind pressure)  =  504 · v² / 10 000      (N/m²),  v = 26 m/s
    lw1 = (P · A · Z) / (g · Δ · 1000)           (wind heeling lever, m)
    lw2 = 1.5 · lw1                              (gust lever)

    Angle of roll  φ₁ = 109 · k · X1 · X2 · sqrt(r · s)    (°)
    (k, X1, X2, r, s are tabulated factors; here we use k = X1 = X2 = 1 and
     r = 0.73 + 0.6·(OG/T), s = 0.035)

We return the main quantities; the accept/reject test is
    Area(b)  ≥  Area(a)
where (a) is the wind-heeling energy beyond the roll-back angle and (b) is
the righting-energy surplus up to 50° (or AVS).
"""

from __future__ import annotations

import numpy as np
from typing import Dict


def weather_criterion(
    displacement_t: float,
    Aw_profile_m2 : float,          # lateral windage area (m²)
    Z_m           : float,          # vertical distance between centre of windage and centre of underwater lateral area
    gz_angles_deg : np.ndarray,
    gz_values_m   : np.ndarray,
    OG_m          : float = 0.0,    # G above waterline (OG > 0) or below (negative)
    draft_m       : float = 1.0,
    wind_speed_mps: float = 26.0,
) -> Dict:
    """
    Returns
    -------
    {
      "lw1": steady wind lever (m),
      "lw2": gust lever (m),
      "phi0": equilibrium angle under lw1 (°),
      "phi1": roll-back angle (°),
      "phi2": second intercept of lw2 with GZ (°),
      "area_a": wind-heeling energy (m·rad),
      "area_b": righting-energy surplus (m·rad),
      "pass"  : area_b ≥ area_a,
    }
    """
    g = 9.81
    P = 504.0 * wind_speed_mps ** 2 / 10000.0            # N/m²
    lw1 = (P * Aw_profile_m2 * Z_m) / (g * displacement_t * 1000.0)
    lw2 = 1.5 * lw1

    ang = gz_angles_deg
    gz  = gz_values_m

    # Find intersections of GZ curve with lw1 and lw2
    def _first_crossing(level: float, start_deg: float = 0.0) -> float:
        mask = ang >= start_deg
        a, g_ = ang[mask], gz[mask]
        for i in range(len(a) - 1):
            if (g_[i] - level) * (g_[i + 1] - level) < 0:
                frac = (level - g_[i]) / (g_[i + 1] - g_[i])
                return float(a[i] + frac * (a[i + 1] - a[i]))
        return float("nan")

    phi0 = _first_crossing(lw1)
    # Roll-back angle (simplified IMO formula, full tables would refine this)
    r = 0.73 + 0.6 * OG_m / max(draft_m, 1e-6)
    s = 0.035
    phi1 = 109.0 * np.sqrt(max(r * s, 0.0))          # degrees, approximate
    phi2 = _first_crossing(lw2, start_deg=phi0 if not np.isnan(phi0) else 0.0)

    def _area(deg_lo: float, deg_hi: float) -> float:
        lo = max(deg_lo, ang[0])
        hi = min(deg_hi, ang[-1])
        if hi <= lo:
            return 0.0
        fine = np.linspace(lo, hi, 201)
        g_   = np.interp(fine, ang, gz)
        return float(np.trapezoid(g_ - lw2, np.radians(fine)))

    phi_start_b = phi0 if not np.isnan(phi0) else 0.0
    phi_end_b   = min(50.0, phi2 if not np.isnan(phi2) else 50.0)
    area_b      = _area(phi_start_b, phi_end_b)

    phi_start_a = phi0 - phi1 if not np.isnan(phi0) else -phi1
    area_a      = -_area(phi_start_a, phi0) if not np.isnan(phi0) else float("nan")

    return {
        "lw1"   : lw1,
        "lw2"   : lw2,
        "phi0_deg": phi0,
        "phi1_deg": phi1,
        "phi2_deg": phi2,
        "area_a_m_rad": area_a,
        "area_b_m_rad": area_b,
        "pass": (not np.isnan(area_a)) and (area_b >= area_a),
    }
