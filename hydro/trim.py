"""
Equilibrium trim solver
=======================

Given a total displacement Δ (tonnes) and longitudinal centre of gravity
LCG (m from AP), solve for the even-keel equivalent mean draft T_m and
trim t = T_F − T_A that put the ship in static equilibrium.

Theory (small-trim approximation, Tupper §4.9)
----------------------------------------------
At any draft:
    Δ = ρ · ∇(T)              (Archimedes)
    MCTC = Δ · GML / (100 · L)
    trim_cm = (LCG − LCB) · Δ / MCTC              →  trim in cm
Then re-linearise about the new mean draft and iterate.

We use a 2-variable Newton-Raphson (on T_m, t) with numerical Jacobian.
Convergence is typically < 10 iterations.
"""

from __future__ import annotations

import numpy as np
from typing import Tuple

from .hull         import Hull
from .hydrostatics import Hydrostatics


# ---------------------------------------------------------------------------

def _residuals(
    hull : Hull,
    T_m  : float,
    trim : float,           # positive = by bow
    W    : float,           # required displacement (t)
    LCG  : float,           # required LCG from AP (m)
    KG   : float,
) -> Tuple[float, float]:
    """
    Effective draft at FP and AP:
        T_F = T_m + trim/2 · (x_F / amidships-distance)   (here amidships = L/2)
        T_A = T_m - trim/2

    For small trim we approximate the heeled hydrostatics by computing
    upright properties at the *mean* draft and using the linear relation
    between trim and the longitudinal moment.
    """
    hs = Hydrostatics(hull, T_m, KG)
    W_calc = hs.displacement
    # Linearised LCG that this mean draft + trim would balance:
    #    trim_cm = (LCG_eff − LCB) · Δ / MCTC
    # we treat trim (m) = trim_cm/100 * L / L = trim_cm / 100  (over LBP).
    # Inverting: LCG_eff = LCB + trim · MCTC · 100 / Δ
    LCG_eff = hs.lcb_from_ap + trim * hs.MCTC * 100.0 / hs.displacement
    return (W_calc - W, LCG_eff - LCG)


def solve_equilibrium(
    hull       : Hull,
    W          : float,
    LCG        : float,
    KG         : float,
    T_guess    : float | None = None,
    trim_guess : float = 0.0,
    tol        : float = 1e-3,
    max_iter   : int   = 40,
) -> dict:
    """
    Newton–Raphson solve for (T_mean, trim_m) such that
        ρ · ∇(T_mean) = W          and      LCG_effective = LCG.

    Returns
    -------
    {
        "T_mean"   : mean draft (m),
        "trim_m"   : trim positive by bow (m),
        "T_F"      : draft at forward perpendicular (m),
        "T_A"      : draft at aft perpendicular     (m),
        "iter"     : iteration count,
        "residual" : (dW, dLCG) at convergence,
        "hydrostatics": Hydrostatics object at T_mean
    }
    """
    T  = T_guess if T_guess is not None else 0.5 * hull.D
    tr = float(trim_guess)

    for k in range(max_iter):
        r0 = np.array(_residuals(hull, T, tr, W, LCG, KG))
        if np.linalg.norm(r0) < tol * max(W, 1.0):
            break

        # Numerical Jacobian (central differences)
        dT  = max(0.002, 0.001 * hull.D)
        dtr = max(0.002, 0.001 * hull.L)
        rT_plus  = np.array(_residuals(hull, T + dT, tr, W, LCG, KG))
        rT_minus = np.array(_residuals(hull, T - dT, tr, W, LCG, KG))
        rt_plus  = np.array(_residuals(hull, T, tr + dtr, W, LCG, KG))
        rt_minus = np.array(_residuals(hull, T, tr - dtr, W, LCG, KG))
        J = np.column_stack([
            (rT_plus  - rT_minus) / (2 * dT),
            (rt_plus  - rt_minus) / (2 * dtr),
        ])
        try:
            step = np.linalg.solve(J, r0)
        except np.linalg.LinAlgError:
            break
        # Limit step size for stability
        T  = float(np.clip(T  - step[0], 0.05, hull.D - 1e-3))
        tr = float(tr - step[1])

    hs = Hydrostatics(hull, T, KG)
    T_F = T + 0.5 * tr
    T_A = T - 0.5 * tr
    return {
        "T_mean"       : T,
        "trim_m"       : tr,
        "T_F"          : T_F,
        "T_A"          : T_A,
        "iter"         : k + 1,
        "residual_W"   : _residuals(hull, T, tr, W, LCG, KG)[0],
        "residual_LCG" : _residuals(hull, T, tr, W, LCG, KG)[1],
        "hydrostatics" : hs,
    }
