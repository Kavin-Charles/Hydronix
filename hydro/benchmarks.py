"""
Benchmark hulls with analytical or published reference data
===========================================================

These are used by the validation suite to verify that our solver reproduces
known answers to within numerical tolerance.

1.  Box barge – rectangular prism, analytical closed form
    ∇   = L · B · T
    Aw  = L · B
    LCB = LCF = L/2     (uniform section)
    KB  = T/2
    IT  = L · B³ / 12  → BM = B² / (12 T)
    Cb = Cw = Cm = Cp = 1

2.  Wigley parabolic hull  (Wigley 1942; classic CFD benchmark)
    y(x, z) = (B/2)·(1 − (2x/L)²)·(1 − (z/T_dmax)²)
    Published hydrostatics for L=2.5 m, B=0.25 m, T=0.15625 m:
        Cb ≈ 0.4444,  Cm ≈ 0.6667  (analytical),  Cp ≈ 0.6667
"""

from __future__ import annotations

import numpy as np
from .hull import Hull


# ---------------------------------------------------------------------------

def box_barge(L: float = 60.0,
              B: float = 12.0,
              D: float = 6.0,
              n_stations: int = 21,
              n_waterlines: int = 13,
              name: str = "Box Barge") -> Hull:
    stations   = np.linspace(0, L, n_stations)
    waterlines = np.linspace(0, D, n_waterlines)
    half_br    = np.full((n_stations, n_waterlines), B / 2.0)
    return Hull(stations, waterlines, half_br, name=name, rho=1.025)


def box_barge_analytical(L: float, B: float, T: float, rho: float = 1.025) -> dict:
    """Closed-form hydrostatics for a box barge at draft T."""
    V  = L * B * T
    return {
        "displacement_m3"   : V,
        "displacement_t"    : rho * V,
        "waterplane_area_m2": L * B,
        "lcb_from_ap_m"     : L / 2.0,
        "lcf_from_ap_m"     : L / 2.0,
        "KB_m"              : T / 2.0,
        "BM_m"              : B ** 2 / (12.0 * T),
        "KM_m"              : T / 2.0 + B ** 2 / (12.0 * T),
        "IT_m4"             : L * B ** 3 / 12.0,
        "IL_m4"             : B * L ** 3 / 12.0,
        "BML_m"             : L ** 2 / (12.0 * T),
        "Cb"                : 1.0,
        "Cw"                : 1.0,
        "Cm"                : 1.0,
        "Cp"                : 1.0,
    }


# ---------------------------------------------------------------------------

def wigley_hull(L: float = 100.0,
                B: float = 10.0,
                D: float = 6.25,
                n_stations: int = 41,
                n_waterlines: int = 21,
                name: str = "Wigley Hull") -> Hull:
    """
    Classical Wigley parabolic hull:
        y(ξ, η) = (B/2) · (1 − ξ²) · (1 − η²)
    with ξ = 2(x − L/2)/L ∈ [−1, 1] and η = z/D ∈ [0, 1].

    At η=1 (top) the hull pinches to zero beam – perfectly parabolic, so
    Simpson's rule will be *exact* to rounding if the grid is fine enough.
    """
    stations   = np.linspace(0, L, n_stations)
    waterlines = np.linspace(0, D, n_waterlines)
    xi  = 2.0 * (stations   - L / 2.0) / L
    eta = waterlines / D
    # Outer product → [n_sta × n_wl]
    half_br = (B / 2.0) * (1.0 - xi[:, None] ** 2) * (1.0 - eta[None, :] ** 2)
    half_br[half_br < 0] = 0.0
    return Hull(stations, waterlines, half_br, name=name, rho=1.025)


def wigley_analytical(L: float, B: float, D: float, T: float,
                      rho: float = 1.025) -> dict:
    """
    Closed-form hydrostatics for the Wigley parabolic hull at draft T.

    Derivation (using η = z/D, ξ = 2(x−L/2)/L):
        Volume = 2 · ∫∫ y dx dz
               = 2 · (B/2) · (L/2) · D · ∫_{-1}^{1}(1−ξ²)dξ · ∫_0^{T/D}(1−η²)dη
               = B · L · D · [4/3] · [η − η³/3]_0^{T/D}
               = (4/3) · B · L · D · (T/D) · [1 − (T/D)²/3]
    """
    u       = T / D
    # Volume = 2 · ∫∫ y dx dz  (full beam = 2× half-breadth)
    #        = (2/3) · B · L · D · u · (1 − u²/3)
    V       = (2.0 / 3.0) * B * L * D * u * (1.0 - u ** 2 / 3.0)
    # Aw(η) = 2 · ∫ y(x, η·D) dx = (2/3) · B · L · (1 − η²)
    Aw      = (2.0 / 3.0) * B * L * (1.0 - u ** 2)
    # KB = ∫ z·Aw(z) dz / V ; Aw(η) = (2/3)·B·L·(1−η²)
    # ∫_0^u η(1−η²)dη = u²/2 − u⁴/4    (numerator factor B·L·D²·(2/3) cancels against V)
    KB = D * (u ** 2 / 2.0 - u ** 4 / 4.0) / (u * (1.0 - u ** 2 / 3.0))
    # IT = (2/3) · ∫ y(x,T)³ dx
    # y(x,T) = (B/2)(1-ξ²)(1-u²)
    # IT = (2/3) · (B/2)³ · (1-u²)³ · (L/2) · ∫_{-1}^{1}(1-ξ²)³ dξ
    #    = (2/3) · (B³/8) · (1-u²)³ · (L/2) · (32/35)
    IT = (2.0 / 3.0) * (B ** 3 / 8.0) * (1.0 - u ** 2) ** 3 * (L / 2.0) * (32.0 / 35.0)
    BM = IT / V
    return {
        "displacement_m3"   : V,
        "displacement_t"    : rho * V,
        "waterplane_area_m2": Aw,
        "KB_m"              : KB,
        "IT_m4"             : IT,
        "BM_m"              : BM,
        "KM_m"              : KB + BM,
        "lcb_from_ap_m"     : L / 2.0,     # by symmetry
        "lcf_from_ap_m"     : L / 2.0,
    }
