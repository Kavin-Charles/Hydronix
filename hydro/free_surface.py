"""
Free-surface correction (FSC)
=============================

Liquid in a partially-filled tank migrates with the heel and reduces the
effective GM.  The classical correction (Tupper §4.6):

    FSM (free-surface moment)  =  ρ_liquid · i
    GG_v (virtual rise in G)   =  FSM / Δ_ship
    GM_corrected               =  GM_initial − GG_v

where `i` is the second moment of the liquid's free surface about its own
centreline (m⁴).
"""

from __future__ import annotations


def fsm_rectangular_tank(
    length_m  : float,
    breadth_m : float,
    rho_liq_t_per_m3: float = 0.85,
) -> float:
    """
    FSM for a rectangular tank with free surface L × B.
    i = L · B³ / 12                 (second moment about centreline)
    FSM = ρ_liq · i                 (tonne·metre units)
    """
    i = length_m * breadth_m ** 3 / 12.0
    return rho_liq_t_per_m3 * i


def gm_corrected(
    gm_initial       : float,
    total_fsm_t_m    : float,
    displacement_t   : float,
) -> float:
    """Effective (fluid) GM after free-surface correction."""
    gg_v = total_fsm_t_m / displacement_t
    return gm_initial - gg_v
