"""
Bonjean curves
==============

For each station, a Bonjean curve is the submerged cross-sectional area
plotted against draft.  Naval architects read displacement and LCB directly
from these curves at any waterline, including trimmed conditions
(`A(x_i, T(x_i))` integrated along the length).

This module returns a dense (n_stations × n_drafts) matrix and a helper
to query the cross-section area at an arbitrary draft per station.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple

from .hull         import Hull
from .integration  import integrate
from shapely.geometry import Polygon


# ---------------------------------------------------------------------------

def bonjean_curves(
    hull  : Hull,
    dT    : float = 0.1,
) -> dict:
    """
    Compute Bonjean curves for every station.

    Parameters
    ----------
    hull : Hull
    dT   : draft resolution (m)

    Returns
    -------
    {
        "stations"  : array of x-positions (m),
        "drafts"    : array of T values (m),
        "area"      : matrix [n_stations × n_drafts] of section area (m²),
        "moment_z"  : matrix of 1st moments about keel (m³)   [for KB per station]
    }
    """
    drafts = np.arange(dT, hull.D + 1e-9, dT)
    n_sta  = len(hull.stations)
    A_mat  = np.zeros((n_sta, len(drafts)))
    M_mat  = np.zeros_like(A_mat)

    for i in range(n_sta):
        poly = hull.section_polygons[i]
        for j, T in enumerate(drafts):
            # Clip polygon at z ≤ T
            y_min, y_max = -hull.B_max, hull.B_max
            clip = Polygon([
                (y_min, -1.0),
                (y_max, -1.0),
                (y_max,   T),
                (y_min,   T),
            ])
            sub = poly.intersection(clip)
            if sub.is_empty:
                continue
            A_mat[i, j] = sub.area
            # 1st moment of area about z = 0 (keel)
            if sub.geom_type == "Polygon":
                c = sub.centroid
                M_mat[i, j] = sub.area * c.y
            else:
                for g in sub.geoms:
                    c = g.centroid
                    M_mat[i, j] += g.area * c.y

    return {
        "stations" : hull.stations,
        "drafts"   : drafts,
        "area"     : A_mat,
        "moment_z" : M_mat,
    }


# ---------------------------------------------------------------------------

def displacement_from_trim(
    hull   : Hull,
    T_A    : float,
    T_F    : float,
    rho    : float | None = None,
) -> Tuple[float, float]:
    """
    Compute displacement Δ and LCB for a ship trimmed T_A → T_F using the
    Bonjean curves: at each station the local draft is a linear function
    of x, and the section area is interpolated from the Bonjean matrix.

    Returns (displacement_t, LCB_from_AP_m).
    """
    rho = rho if rho is not None else hull.rho
    data = bonjean_curves(hull)
    x    = data["stations"]
    T_x  = T_A + (T_F - T_A) * (x - x[0]) / (x[-1] - x[0])

    A_x = np.zeros_like(x)
    for i in range(len(x)):
        A_x[i] = np.interp(T_x[i], data["drafts"], data["area"][i])

    V   = integrate(x, A_x)
    LCB = integrate(x, A_x * x) / V
    return rho * V, LCB
