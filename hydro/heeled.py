"""
TRUE heeled hydrostatics via polygon clipping
---------------------------------------------

This module computes stability parameters **without the wall-sided
approximation**.  For each heel angle φ:

  1.  Each station cross-section (a Shapely polygon in body-fixed (y,z)
      coordinates) is intersected with the heeled waterline half-plane
              z  ≤  T + y · tan(φ)
      giving the *actual* submerged section.
  2.  The submerged volume  ∇(T,φ)  is obtained by integrating the
      submerged section areas along the length (Simpson).
  3.  The mean draft  T  is iterated (secant method, bracketed) so that
      ∇(T,φ) equals the upright displacement ∇₀  – i.e. constant
      displacement as the ship heels (physically correct: the ship rotates
      about its metacentre, total weight unchanged).
  4.  The centre of buoyancy  B  of the submerged volume is found by
      taking the area-weighted centroid of each submerged section,
      integrated along the length.
  5.  GZ is the *horizontal* distance from G to B in the earth-fixed
      frame:
              GZ  =  B_y · cos(φ)  +  (B_z − KG) · sin(φ)
      where (B_y, B_z) are the body-fixed centre of buoyancy coordinates.
      Sign: +φ heels starboard (+y side) down; y_B shifts to +y; B rises
      slightly so (z_B − KG)·sin(φ) < 0 typically, reducing GZ below the
      first-order GM·sin(φ).

This is exactly the calculation performed by NAPA / GHS / Maxsurf, only
simplified to a constant-draft, even-keel base state.
"""

from __future__ import annotations

import numpy as np
from functools import cached_property
from typing import List, Tuple

from shapely.geometry import Polygon, Point
from shapely.geometry.polygon   import orient
from shapely.ops     import unary_union

from .hull         import Hull
from .hydrostatics import Hydrostatics
from .integration  import integrate, moment


# ---------------------------------------------------------------------------
# Low-level geometric helpers
# ---------------------------------------------------------------------------

def _centroid_xy(poly) -> Tuple[float, float]:
    """
    Centroid of a (possibly empty / MultiPolygon) Shapely geometry in its
    own 2-D plane.  Returns (0, 0) for empty geometry.
    """
    if poly.is_empty:
        return 0.0, 0.0
    if poly.geom_type == "Polygon":
        c = poly.centroid
        return c.x, c.y
    # MultiPolygon – area-weighted
    total_area = poly.area
    if total_area == 0.0:
        return 0.0, 0.0
    sx = sy = 0.0
    for g in poly.geoms:
        c = g.centroid
        sx += c.x * g.area
        sy += c.y * g.area
    return sx / total_area, sy / total_area


# ---------------------------------------------------------------------------
# Heeled hydrostatics calculator (constant displacement)
# ---------------------------------------------------------------------------

class HeeledHydrostatics:
    """
    Compute submerged-volume properties of a hull heeled to angle φ.

    The mean draft T is adjusted so that the displaced volume equals
    `target_volume` (defaults to the upright displacement).

    Attributes
    ----------
    hull   : Hull
    heel_deg : heel angle (°)  (positive = starboard side down)
    target_volume : volume to preserve (m³)
    KG     : VCG of the ship (m)
    draft_mean : equilibrium mean draft (m, solved internally)
    """

    def __init__(
        self,
        hull          : Hull,
        heel_deg      : float,
        target_volume : float,
        KG            : float,
        draft_upright : float,
    ):
        self.hull           = hull
        self.heel_deg       = float(heel_deg)
        self.target_volume  = float(target_volume)
        self.KG             = float(KG)
        self.draft_upright  = float(draft_upright)
        self.draft_mean     = self._solve_draft()

    # ------------------------------------------------------------------

    def _volume_at(self, draft_mean: float) -> float:
        """Displaced volume with heeled waterline passing at mean draft."""
        As = np.array([
            self.hull.submerged_section_heeled(i, draft_mean, self.heel_deg).area
            for i in range(len(self.hull.stations))
        ])
        return integrate(self.hull.stations, As)

    def _solve_draft(self) -> float:
        """
        Find the mean draft (height of waterline at y=0) such that the
        displaced volume equals `target_volume`.  Uses bracketed secant
        on a monotonic function.
        """
        # Bracket search: start at upright draft, widen if needed
        T_lo = max(0.05, 0.2 * self.draft_upright)
        T_hi = min(self.hull.D, 1.8 * self.draft_upright)

        f_lo = self._volume_at(T_lo) - self.target_volume
        f_hi = self._volume_at(T_hi) - self.target_volume
        iters = 0
        while f_lo * f_hi > 0 and iters < 20:
            T_hi = min(self.hull.D, T_hi + 0.5 * self.hull.D)
            T_lo = max(0.01, T_lo - 0.5 * self.hull.D)
            f_lo = self._volume_at(T_lo) - self.target_volume
            f_hi = self._volume_at(T_hi) - self.target_volume
            iters += 1

        # Bisection/secant hybrid (bisection for robustness)
        for _ in range(60):
            T_mid = 0.5 * (T_lo + T_hi)
            f_mid = self._volume_at(T_mid) - self.target_volume
            if abs(f_mid) < 1e-4 * self.target_volume:
                return T_mid
            if f_lo * f_mid < 0:
                T_hi, f_hi = T_mid, f_mid
            else:
                T_lo, f_lo = T_mid, f_mid
        return 0.5 * (T_lo + T_hi)

    # ------------------------------------------------------------------

    @cached_property
    def submerged_sections(self) -> List:
        return [
            self.hull.submerged_section_heeled(i, self.draft_mean, self.heel_deg)
            for i in range(len(self.hull.stations))
        ]

    @cached_property
    def section_areas(self) -> np.ndarray:
        return np.array([s.area for s in self.submerged_sections])

    @cached_property
    def section_centroids_yz(self) -> np.ndarray:
        """
        Area-weighted (y, z) centroid of each submerged section, in body-fixed
        coordinates.  Empty sections return (0, 0) which are harmless because
        they're weighted by zero area.
        """
        return np.array([_centroid_xy(s) for s in self.submerged_sections])

    @cached_property
    def displacement_volume(self) -> float:
        return integrate(self.hull.stations, self.section_areas)

    # Buoyancy centre in body-fixed frame
    @cached_property
    def B_body(self) -> Tuple[float, float, float]:
        """(x_B, y_B, z_B) in body-fixed coordinates, all in metres."""
        A     = self.section_areas
        cyz   = self.section_centroids_yz
        stat  = self.hull.stations
        x_B   = moment(stat, A, stat) / self.displacement_volume
        y_B   = moment(stat, A, cyz[:, 0]) / self.displacement_volume
        z_B   = moment(stat, A, cyz[:, 1]) / self.displacement_volume
        return x_B, y_B, z_B

    # ------------------------------------------------------------------
    # The deliverables: GZ, KN
    # ------------------------------------------------------------------

    @property
    def GZ(self) -> float:
        """
        Righting lever arm from the TRUE heeled condition.

        In the body-fixed frame the centre of buoyancy is (y_B, z_B).
        The centre of gravity is at (0, KG).  The vertical in the earth
        frame makes an angle φ with the body-z axis, so the horizontal
        (earth-frame) distance from G to B is

            GZ =  y_B · cos(φ)  −  (z_B − KG) · sin(φ)

        (Positive GZ → righting;  negative → capsizing.)
        """
        phi          = np.radians(self.heel_deg)
        _, y_B, z_B  = self.B_body
        return y_B * np.cos(phi) + (z_B - self.KG) * np.sin(phi)

    @property
    def KN(self) -> float:
        """
        KN righting lever measured from the keel (KG = 0 reference).
        KN  =  y_B · cos(φ)  −  z_B · sin(φ)  +  KG · sin(φ) + GZ (≡ y_B cosφ − z_B sinφ)
        Equivalently:  KN = GZ + KG · sin(φ).
        """
        return self.GZ + self.KG * np.sin(np.radians(self.heel_deg))


# ---------------------------------------------------------------------------
# GZ / KN curves at all angles
# ---------------------------------------------------------------------------

def gz_curve_true(
    hull      : Hull,
    draft     : float,
    KG        : float,
    angles_deg: np.ndarray | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    True-heeled GZ curve (no wall-sided assumption).  Displacement is held
    constant equal to the upright value; mean draft is solved at each angle.
    """
    if angles_deg is None:
        angles_deg = np.arange(0.0, 81.0, 5.0)
    angles_deg = np.asarray(angles_deg, dtype=float)

    base = Hydrostatics(hull, draft, KG)
    V0   = base.displacement_volume

    gz = np.zeros_like(angles_deg, dtype=float)
    for k, phi in enumerate(angles_deg):
        if phi == 0.0:
            gz[k] = 0.0
            continue
        hh = HeeledHydrostatics(hull, phi, V0, KG, draft)
        gz[k] = hh.GZ
    return angles_deg, gz


def kn_curve_true(
    hull      : Hull,
    draft     : float,
    KG        : float,
    angles_deg: np.ndarray | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """True KN curve (measured from keel).  KN = GZ + KG·sin(φ)."""
    ang, gz = gz_curve_true(hull, draft, KG, angles_deg)
    kn = gz + KG * np.sin(np.radians(ang))
    return ang, kn


# ---------------------------------------------------------------------------
# Cross-curves of stability – KN versus displacement at fixed heel angles
# ---------------------------------------------------------------------------

def cross_curves_true(
    hull        : Hull,
    drafts      : List[float],
    KG          : float,
    angles_deg  : List[float] | None = None,
) -> dict:
    if angles_deg is None:
        angles_deg = [10, 20, 30, 40, 50, 60, 70, 80]
    displacements = []
    kn_matrix     = {a: [] for a in angles_deg}

    for T in sorted(drafts):
        base = Hydrostatics(hull, T, KG)
        displacements.append(base.displacement)
        ang, kn = kn_curve_true(hull, T, KG, np.array(angles_deg, float))
        for a, k in zip(ang, kn):
            kn_matrix[float(a)].append(float(k))

    return {
        "displacements_t": displacements,
        "angles_deg"    : angles_deg,
        "kn_matrix"     : [kn_matrix[float(a)] for a in angles_deg],
    }
