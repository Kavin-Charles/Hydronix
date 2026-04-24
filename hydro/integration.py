"""
Numerical integration rules used in naval architecture.

Implements Simpson's 1st rule (1/3), 2nd rule (3/8), and the 5-8-(-1) rule
exactly as presented in standard naval-architecture texts (e.g. Tupper,
"Introduction to Naval Architecture"; Barrass, "Ship Stability for
Masters and Mates"; Biran, "Ship Hydrostatics and Stability").

All routines handle the three common cases that occur on an offset table:

  * number of intervals n is EVEN        →  composite Simpson 1/3 (exact for cubics)
  * n is odd and n ≥ 3                   →  Simpson 1/3 on first n-3, Simpson 3/8 on last 3
  * n == 1                               →  trapezoidal

For irregularly-spaced abscissae we fall back to composite trapezoidal, which
is the correct numerically-stable choice – applying Simpson's rule naïvely to
unequally-spaced data introduces O(h) bias.
"""

from __future__ import annotations

import numpy as np
from typing import Sequence


# ---------------------------------------------------------------------------
# Primitive rules
# ---------------------------------------------------------------------------

def _simpson_13(y: np.ndarray, h: float) -> float:
    """Composite Simpson's 1/3 rule, n intervals, n even, equal spacing h."""
    n = len(y) - 1
    assert n >= 2 and n % 2 == 0, "Simpson 1/3 requires an even number of intervals"
    w       = np.ones_like(y, dtype=float)
    w[1:-1:2] = 4.0    # odd indices
    w[2:-1:2] = 2.0    # even indices (not end-points)
    return h / 3.0 * float(np.dot(w, y))


def _simpson_38(y: np.ndarray, h: float) -> float:
    """Simpson's 3/8 rule over exactly 3 intervals (4 ordinates), equal spacing h."""
    assert len(y) == 4
    return 3.0 * h / 8.0 * (y[0] + 3.0 * y[1] + 3.0 * y[2] + y[3])


def _trapezoidal_uniform(y: np.ndarray, h: float) -> float:
    return h * (0.5 * y[0] + y[1:-1].sum() + 0.5 * y[-1])


# ---------------------------------------------------------------------------
# Five-eight minus one rule  (for evaluating an integral up to an interior
# ordinate given three equally-spaced data points)
# ---------------------------------------------------------------------------

def five_eight_minus_one(y0: float, y1: float, y2: float, h: float) -> float:
    """
    Integral from x0 to x1 (first panel only) using the 5-8-(-1) rule:

        ∫_{x0}^{x1} y dx  ≈  h/12 · ( 5 y0 + 8 y1 − y2 )

    Useful for computing the moment of a curve between the first two ordinates
    (e.g. estimating draft integrals up to an arbitrary height in a fine grid).
    """
    return h / 12.0 * (5.0 * y0 + 8.0 * y1 - y2)


# ---------------------------------------------------------------------------
# Adaptive composite integrator (public API)
# ---------------------------------------------------------------------------

def integrate(x: Sequence[float], y: Sequence[float]) -> float:
    """
    Composite Simpson where possible, else trapezoidal.

    Parameters
    ----------
    x : abscissae (monotonic)
    y : ordinates

    Returns
    -------
    float  –  ∫ y dx from x[0] to x[-1]
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n_int = len(x) - 1
    if n_int <= 0:
        return 0.0
    if n_int == 1:
        return 0.5 * (x[1] - x[0]) * (y[0] + y[1])

    h = np.diff(x)
    if not np.allclose(h, h[0], rtol=1e-4):
        return float(np.trapezoid(y, x))

    h0 = h[0]
    if n_int % 2 == 0:
        return _simpson_13(y, h0)

    # n_int is odd and >= 3: Simpson 1/3 on first n_int-3 intervals,
    # then Simpson 3/8 on the last 3 intervals.  Total is exact for cubics.
    if n_int == 3:
        return _simpson_38(y, h0)
    part1 = _simpson_13(y[: -3], h0)
    part2 = _simpson_38(y[-4:], h0)
    return part1 + part2


# ---------------------------------------------------------------------------
# Moment integrators – these evaluate  ∫ y(x) · f(x) dx  for commonly-needed f
# ---------------------------------------------------------------------------

def moment(x: Sequence[float], y: Sequence[float], arm: Sequence[float]) -> float:
    """Integral of y(x)·arm(x) dx."""
    x, y, arm = (np.asarray(v, float) for v in (x, y, arm))
    return integrate(x, y * arm)


def second_moment(x: Sequence[float], y: Sequence[float], arm: Sequence[float]) -> float:
    """Integral of y(x)·arm(x)² dx."""
    x, y, arm = (np.asarray(v, float) for v in (x, y, arm))
    return integrate(x, y * arm * arm)


# ---------------------------------------------------------------------------
# Richardson extrapolation – convergence study for reporting error bars
# ---------------------------------------------------------------------------

def richardson_estimate(x: Sequence[float], y: Sequence[float]) -> dict:
    """
    Estimate integration error by Richardson extrapolation.

    Returns a dict with:
        I_h    : integral on the supplied grid
        I_h2   : integral on every 2nd point (coarser grid)
        error  : estimate of absolute error in I_h (Richardson residual)
        order  : empirical order of convergence
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 5 or (len(x) - 1) % 2 != 0:
        return {"I_h": integrate(x, y), "I_h2": float("nan"),
                "error": float("nan"), "order": float("nan")}
    I_h  = integrate(x, y)
    I_h2 = integrate(x[::2], y[::2])
    # Simpson is 4th order, so error ≈ (I_h − I_h2) / (2^4 − 1)
    err  = (I_h - I_h2) / 15.0
    return {"I_h": I_h, "I_h2": I_h2, "error": abs(err), "order": 4.0}


# ---------------------------------------------------------------------------
# Convenience: Simpson's Multipliers (for textbook-style tables)
# ---------------------------------------------------------------------------

def simpson_multipliers(n_stations: int) -> np.ndarray:
    """
    Return the Simpson's Multiplier (SM) vector for n_stations ordinates so
    that  Σ SM_i · y_i · h / 3  gives the integral.

    Picks Simpson 1/3 for even number of intervals, switches to 3/8 for the
    last 3 intervals when the count is odd (standard naval-arch convention).
    """
    n_int = n_stations - 1
    sm = np.zeros(n_stations)
    if n_int <= 0:
        return sm
    if n_int == 1:
        sm[:] = [1.5, 1.5]           # trapezoidal scaled by 3/h so ·h/3 gives trap
        return sm
    if n_int % 2 == 0:
        sm[0]  = 1.0
        sm[-1] = 1.0
        sm[1:-1:2] = 4.0
        sm[2:-1:2] = 2.0
        return sm
    # odd: 1/3 on first block + 3/8 on last 3 intervals
    if n_int == 3:
        sm[:] = [1.125, 3.375, 3.375, 1.125]   # = 3/8 · (3/h · h)/3 factor
        return sm
    # combine
    sm[0]     = 1.0
    sm[1:-4:2] = 4.0
    sm[2:-4:2] = 2.0
    # junction point between 1/3 and 3/8
    sm[-4]   += 1.0 + 1.125
    sm[-3]    = 3.375
    sm[-2]    = 3.375
    sm[-1]    = 1.125
    return sm
