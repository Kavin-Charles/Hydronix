"""
Stability analysis – wall-sided closed-form formula and curve-level metrics.

For TRUE heeled stability (no wall-sided assumption) see `hydro.heeled`.
This module is retained because:
    * the wall-sided formula gives an analytic benchmark for small angles
    * the derived parameters (GZmax, AVS, righting-energy areas) are
      algorithm-agnostic and used by the IMO criteria checker.
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Tuple

from .hydrostatics import Hydrostatics


# ---------------------------------------------------------------------------
# Wall-sided GZ (small-angle analytical benchmark)
# ---------------------------------------------------------------------------

def gz_curve_wallsided(
    hs          : Hydrostatics,
    angles_deg  : Optional[np.ndarray] = None,
    limit_deg   : float = 25.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Wall-sided formula (Biran §3.7; Tupper §4):

        GZ(φ)  =  sin(φ) · [ GM  +  ½ · BM · tan²(φ) ]

    Valid only while the deck edge stays out of water and the bilge stays
    submerged – a handful of degrees for real ships.  Returned as NaN
    beyond `limit_deg` to discourage misuse.
    """
    if angles_deg is None:
        angles_deg = np.arange(0, 41, 5, dtype=float)
    phi = np.radians(angles_deg)
    gz  = np.sin(phi) * (hs.GM + 0.5 * hs.BM * np.tan(phi) ** 2)
    gz[angles_deg > limit_deg] = np.nan
    return angles_deg, gz


# ---------------------------------------------------------------------------
# Curve-level stability parameters
# ---------------------------------------------------------------------------

def stability_parameters(
    angles_deg : np.ndarray,
    gz         : np.ndarray,
    gm         : float,
) -> dict:
    """
    Derive curve-level stability quantities required by IMO A.749:
        * GZ at 30° and 40°
        * Maximum GZ and the heel angle at which it occurs
        * Righting-energy areas 0–30°, 0–40°, 30–40°  (m · rad)
        * Angle of vanishing stability (AVS) and range of positive stability
    """
    angles_deg = np.asarray(angles_deg, dtype=float)
    gz         = np.asarray(gz,         dtype=float)
    valid  = ~np.isnan(gz)
    ang    = angles_deg[valid]
    gz_v   = gz[valid]

    def _interp(deg: float) -> float:
        if ang[0] > deg or ang[-1] < deg:
            return float("nan")
        return float(np.interp(deg, ang, gz_v))

    gz30 = _interp(30.0)
    gz40 = _interp(40.0)

    imax      = int(np.argmax(gz_v))
    gz_max    = float(gz_v[imax])
    ang_gmax  = float(ang[imax])

    def _area(deg_lo: float, deg_hi: float) -> float:
        lo = max(deg_lo, ang[0])
        hi = min(deg_hi, ang[-1])
        if hi <= lo:
            return float("nan")
        # Dense sample for accurate trapezoid
        fine = np.linspace(lo, hi, 201)
        g    = np.interp(fine, ang, gz_v)
        return float(np.trapezoid(g, np.radians(fine)))

    # Angle of vanishing stability: first zero crossing after GZmax
    avs = float("nan")
    for i in range(imax, len(ang) - 1):
        if gz_v[i] >= 0.0 >= gz_v[i + 1]:
            frac = gz_v[i] / (gz_v[i] - gz_v[i + 1])
            avs  = ang[i] + frac * (ang[i + 1] - ang[i])
            break

    return {
        "GM_m"              : gm,
        "GZ_at_30deg_m"     : gz30,
        "GZ_at_40deg_m"     : gz40,
        "max_GZ_m"          : gz_max,
        "angle_max_GZ_deg"  : ang_gmax,
        "area_0_30_m_rad"   : _area(0.0, 30.0),
        "area_0_40_m_rad"   : _area(0.0, 40.0),
        "area_30_40_m_rad"  : _area(30.0, 40.0),
        "angle_vanishing_deg": avs,
        "range_positive_deg": avs if not np.isnan(avs) else float("nan"),
    }
