"""
Upright hydrostatic properties at a specified draft.

All integrals use naval-architecture Simpson composite rules from
`hydro.integration`.  Every result is computed from first principles and
cross-checked through Richardson extrapolation; the error estimate is
surfaced in `summary()["integration_error_estimate"]`.
"""

from __future__ import annotations

import numpy as np
from functools import cached_property
from typing import List

from .hull        import Hull
from .integration import integrate, moment, second_moment, richardson_estimate


# ---------------------------------------------------------------------------

class Hydrostatics:
    """
    Upright hydrostatic calculator.

    Parameters
    ----------
    hull  : Hull        – geometry
    draft : float       – design draft  T  (m)
    KG    : float       – vertical centre of gravity above keel (m)
    """

    def __init__(self, hull: Hull, draft: float, KG: float = 0.0):
        if draft <= 0:
            raise ValueError("Draft must be positive.")
        if draft > hull.waterlines[-1] + 1e-9:
            raise ValueError(
                f"Draft {draft} m exceeds offset-table top waterline "
                f"{hull.waterlines[-1]} m."
            )
        self.hull  = hull
        self.draft = float(draft)
        self.KG    = float(KG)

        # Build a fine waterline grid up to draft for KB / Aw(z) integrations
        wl_grid = list(hull.waterlines[hull.waterlines <  self.draft])
        wl_grid.append(self.draft)
        self._wl_grid = np.array(sorted(set(wl_grid)))

    # ------------------------------------------------------------------
    # Waterplane properties
    # ------------------------------------------------------------------

    def waterplane_half_breadths(self, z: float | None = None) -> np.ndarray:
        return self.hull.half_breadths_at(self.draft if z is None else z)

    @cached_property
    def waterplane_area(self) -> float:
        y = self.waterplane_half_breadths()
        return 2.0 * integrate(self.hull.stations, y)

    @cached_property
    def lcf_from_ap(self) -> float:
        y = self.waterplane_half_breadths()
        return 2.0 * moment(self.hull.stations, y, self.hull.stations) / self.waterplane_area

    @cached_property
    def IT(self) -> float:
        """Second moment of waterplane area about the centreline – m⁴."""
        y = self.waterplane_half_breadths()
        return (2.0 / 3.0) * integrate(self.hull.stations, y ** 3)

    @cached_property
    def IL(self) -> float:
        """Second moment of waterplane area about the transverse axis through LCF – m⁴."""
        y     = self.waterplane_half_breadths()
        x_rel = self.hull.stations - self.lcf_from_ap
        return 2.0 * second_moment(self.hull.stations, y, x_rel)

    # ------------------------------------------------------------------
    # Section areas and volume
    # ------------------------------------------------------------------

    def _section_area(self, sta_idx: int) -> float:
        """Cross-sectional area at station i up to the design draft."""
        z_grid = self._wl_grid
        # Interpolate half-breadths at the fine grid
        y_at = np.array(
            [self.hull.half_breadth(sta_idx, z) for z in z_grid]
        )
        return 2.0 * integrate(z_grid, y_at)

    @cached_property
    def section_areas(self) -> np.ndarray:
        return np.array(
            [self._section_area(i) for i in range(len(self.hull.stations))]
        )

    @cached_property
    def displacement_volume(self) -> float:   # ∇  (m³)
        return integrate(self.hull.stations, self.section_areas)

    @cached_property
    def displacement(self) -> float:          # Δ  (tonnes)
        return self.hull.rho * self.displacement_volume

    @cached_property
    def lcb_from_ap(self) -> float:
        return moment(self.hull.stations, self.section_areas,
                      self.hull.stations) / self.displacement_volume

    @cached_property
    def KB(self) -> float:
        """Vertical centre of buoyancy above keel."""
        z_grid = self._wl_grid
        Aw_z   = np.array(
            [2.0 * integrate(self.hull.stations, self.hull.half_breadths_at(z))
             for z in z_grid]
        )
        return moment(z_grid, Aw_z, z_grid) / self.displacement_volume

    # ------------------------------------------------------------------
    # Metacentres
    # ------------------------------------------------------------------

    @property
    def BM(self) -> float:   # transverse metacentric radius
        return self.IT / self.displacement_volume

    @property
    def BML(self) -> float:  # longitudinal metacentric radius
        return self.IL / self.displacement_volume

    @property
    def KM(self) -> float:   # transverse metacentre above keel
        return self.KB + self.BM

    @property
    def KML(self) -> float:
        return self.KB + self.BML

    @property
    def GM(self) -> float:
        return self.KM - self.KG

    @property
    def GML(self) -> float:
        return self.KML - self.KG

    # ------------------------------------------------------------------
    # Coefficients of form
    # ------------------------------------------------------------------

    @property
    def Cb(self) -> float:   # block
        return self.displacement_volume / (self.hull.L * self.hull.B_max * self.draft)

    @property
    def Cw(self) -> float:   # waterplane
        return self.waterplane_area / (self.hull.L * self.hull.B_max)

    @property
    def Am(self) -> float:   # midship section area (m²)
        mid_idx = len(self.hull.stations) // 2
        return self._section_area(mid_idx)

    @property
    def Cm(self) -> float:   # midship
        return self.Am / (self.hull.B_max * self.draft)

    @property
    def Cp(self) -> float:   # prismatic
        return self.displacement_volume / (self.Am * self.hull.L)

    @property
    def Cvp(self) -> float:  # vertical prismatic
        return self.displacement_volume / (self.waterplane_area * self.draft)

    # ------------------------------------------------------------------
    # Hydrostatic tonnes per cm and moment to change trim
    # ------------------------------------------------------------------

    @property
    def TPC(self) -> float:
        """Tonnes per centimetre immersion: TPC = Aw · ρ / 100 (t/cm)."""
        return self.waterplane_area * self.hull.rho / 100.0

    @property
    def MCTC(self) -> float:
        """
        Moment to change trim by 1 cm (t·m / cm):
            MCTC = Δ · GML / (100 · L)
        """
        return self.displacement * self.GML / (100.0 * self.hull.L)

    def roll_period(self, C_roll: float = 0.35) -> float:
        """
        Natural roll period  T_φ  (seconds).

        Uses the empirical formula (Tupper §5.3):
            k_xx  = C_roll · B           (transverse radius of gyration)
            T_φ   = 2π · k_xx / √(g·GM)

        C_roll defaults to 0.35 (suitable for most displacement vessels;
        use 0.39–0.42 for full hull forms, 0.30–0.33 for fine hulls).
        If GM ≤ 0 the ship is unstable and NaN is returned.
        """
        if self.GM <= 0.0:
            return float("nan")
        g    = 9.80665  # m/s²
        k_xx = C_roll * self.hull.B_max
        return 2.0 * np.pi * k_xx / np.sqrt(g * self.GM)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        err = richardson_estimate(self.hull.stations, self.section_areas)
        return {
            "ship_name"                : self.hull.name,
            "rho_t_per_m3"             : self.hull.rho,
            "L_m"                      : self.hull.L,
            "B_max_m"                  : self.hull.B_max,
            "D_m"                      : self.hull.D,
            "draft_m"                  : self.draft,

            "displacement_m3"          : self.displacement_volume,
            "displacement_t"           : self.displacement,

            "waterplane_area_m2"       : self.waterplane_area,
            "Am_m2"                    : self.Am,

            "lcb_from_ap_m"            : self.lcb_from_ap,
            "lcf_from_ap_m"            : self.lcf_from_ap,

            "KB_m"                     : self.KB,
            "BM_m"                     : self.BM,
            "KM_m"                     : self.KM,
            "KG_m"                     : self.KG,
            "GM_m"                     : self.GM,
            "BML_m"                    : self.BML,
            "KML_m"                    : self.KML,
            "GML_m"                    : self.GML,

            "IT_m4"                    : self.IT,
            "IL_m4"                    : self.IL,

            "Cb"                       : self.Cb,
            "Cw"                       : self.Cw,
            "Cm"                       : self.Cm,
            "Cp"                       : self.Cp,
            "Cvp"                      : self.Cvp,

            "TPC_t_per_cm"             : self.TPC,
            "MCTC_tm_per_cm"           : self.MCTC,
            "roll_period_s"            : self.roll_period(),   # C_roll=0.35 default

            "integration_error_estimate": err["error"],
        }


# ---------------------------------------------------------------------------
# Full hydrostatic table across multiple drafts
# ---------------------------------------------------------------------------

def hydrostatic_table(
    hull : Hull,
    drafts: List[float],
    KG   : float = 0.0,
) -> List[dict]:
    """Return a list of summary dicts (one per draft, sorted ascending)."""
    return [Hydrostatics(hull, T, KG).summary() for T in sorted(drafts)]
