"""
Hull geometry: offset table, station polygons, and queries.

A Hull is represented by
    * stations        – longitudinal positions (m) from AP → FP
    * waterlines      – vertical heights      (m) from keel upward
    * half_breadths   – [n_stations × n_waterlines] matrix y(x_i, z_j)  (m)

Each station carries a Shapely polygon describing the *full* cross-section
(mirrored port/starboard about the centreline), clipped up to the highest
waterline.  These polygons are the workhorse for heeled hydrostatics.

The class is deliberately immutable once constructed; derived data is cached.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from functools import cached_property
from typing import List, Sequence, Tuple

from shapely.geometry import Polygon, Point


# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Hull:
    stations       : np.ndarray          # shape (N,)   – m from AP
    waterlines     : np.ndarray          # shape (M,)   – m from keel
    half_breadths  : np.ndarray          # shape (N, M) – m
    name           : str   = "Ship"
    rho            : float = 1.025       # t/m³ (seawater default)

    # ------------------------------------------------------------------

    def __post_init__(self):
        # Cast to arrays (dataclass-frozen hack via object.__setattr__)
        object.__setattr__(self, "stations",
                           np.asarray(self.stations, dtype=float))
        object.__setattr__(self, "waterlines",
                           np.asarray(self.waterlines, dtype=float))
        object.__setattr__(self, "half_breadths",
                           np.asarray(self.half_breadths, dtype=float))

        if self.half_breadths.shape != (len(self.stations), len(self.waterlines)):
            raise ValueError(
                f"half_breadths shape {self.half_breadths.shape} "
                f"does not match (n_stations={len(self.stations)}, "
                f"n_waterlines={len(self.waterlines)})."
            )
        if not np.all(np.diff(self.stations) > 0):
            raise ValueError("stations must be strictly increasing.")
        if not np.all(np.diff(self.waterlines) >= 0):
            raise ValueError("waterlines must be non-decreasing.")
        if np.any(self.half_breadths < 0):
            raise ValueError("half_breadths must be non-negative.")

    # ------------------------------------------------------------------
    # Basic particulars
    # ------------------------------------------------------------------

    @property
    def L(self) -> float:
        """Length between AP (first station) and FP (last station) – m."""
        return float(self.stations[-1] - self.stations[0])

    @property
    def B_max(self) -> float:
        """Maximum moulded breadth (2 × max half-breadth) – m."""
        return 2.0 * float(self.half_breadths.max())

    @property
    def D(self) -> float:
        """Moulded depth: highest waterline in the offset table – m."""
        return float(self.waterlines[-1])

    @property
    def amidships(self) -> float:
        """x-coordinate of amidships (half of LBP measured from AP)."""
        return 0.5 * (self.stations[0] + self.stations[-1])

    # ------------------------------------------------------------------
    # Half-breadth queries
    # ------------------------------------------------------------------

    def half_breadth(self, station_idx: int, z: float) -> float:
        """Linear-interpolated half-breadth at station i, height z (m)."""
        return float(np.interp(z, self.waterlines,
                               self.half_breadths[station_idx]))

    def half_breadths_at(self, z: float) -> np.ndarray:
        """Half-breadths at every station for a single waterline height z."""
        return np.array(
            [self.half_breadth(i, z) for i in range(len(self.stations))]
        )

    # ------------------------------------------------------------------
    # Section polygons  (the heart of the heeled-hydrostatics engine)
    # ------------------------------------------------------------------

    @cached_property
    def section_polygons(self) -> List[Polygon]:
        """
        One Shapely polygon per station representing the full moulded cross
        section up to the highest waterline, mirrored about the centreline
        (y = 0).  Polygon coordinates are (y, z).

        Construction:
            starboard side  (y ≥ 0) : (+hb(z_j), z_j) for j = 0 … M-1
            port side       (y ≤ 0) : (−hb(z_j), z_j) traversed downward
            closed at keel point (0, z_keel)
        """
        polygons: List[Polygon] = []
        z_vals  = self.waterlines
        for i in range(len(self.stations)):
            hb = self.half_breadths[i]
            # Starboard edge (bottom to top)
            stb = [(float(hb[j]),  float(z_vals[j])) for j in range(len(z_vals))]
            # Port edge (top to bottom, mirrored)
            prt = [(-float(hb[j]), float(z_vals[j])) for j in range(len(z_vals) - 1, -1, -1)]
            ring = stb + prt
            # Ensure it's a valid closed ring; Shapely closes automatically
            poly = Polygon(ring)
            if not poly.is_valid:
                # Repair self-intersections with zero-buffer trick
                poly = poly.buffer(0)
            polygons.append(poly)
        return polygons

    # ------------------------------------------------------------------
    # Submerged section at a given upright waterline (draft)
    # ------------------------------------------------------------------

    def submerged_section_upright(self, station_idx: int, draft: float) -> Polygon:
        """Section polygon clipped to z ≤ draft (upright condition)."""
        poly = self.section_polygons[station_idx]
        # Clipping polygon: (−∞, −∞) → (+∞, draft)   (a big rectangle)
        y_min, y_max = -self.B_max, self.B_max
        z_min        = float(self.waterlines[0]) - 1.0
        clip = Polygon([(y_min, z_min), (y_max, z_min),
                        (y_max, draft), (y_min, draft)])
        return poly.intersection(clip)

    # ------------------------------------------------------------------
    # Submerged section at a heeled waterline
    # ------------------------------------------------------------------

    def submerged_section_heeled(
        self,
        station_idx: int,
        draft      : float,
        heel_deg   : float,
        lcf_y      : float = 0.0,
    ) -> Polygon:
        """
        Section polygon clipped by the heeled waterline.

        The heeled waterline in body-fixed coordinates is the straight line

            z_body  =  T  +  (y − y_LCF) · tan(φ)

        Sign convention: φ > 0 means the ship heels to starboard (+y side),
        so the starboard edge goes DEEPER into the water – the submerged
        region (below the line) is therefore LARGER at +y and SMALLER at −y.
        Parallel sinkage is modelled by adjusting T.
        """
        poly  = self.section_polygons[station_idx]
        phi   = np.radians(heel_deg)

        # Build a large clipping polygon for the half-plane
        #     z  ≤  draft − (y − lcf_y) · tan(φ)
        # Use bounds that encompass the hull with a big margin so that the
        # quadrilateral stays simple (non-self-intersecting) at all heels.
        span   = max(self.B_max, self.D) * 20.0 + 50.0
        y_min, y_max = -span, span
        z_bot  = -span

        tan_phi = np.tan(phi)
        z_left  = draft + (y_min - lcf_y) * tan_phi
        z_right = draft + (y_max - lcf_y) * tan_phi

        clip = Polygon([
            (y_min, z_bot),
            (y_max, z_bot),
            (y_max, z_right),
            (y_min, z_left),
        ])
        if not clip.is_valid:
            clip = clip.buffer(0)
        return poly.intersection(clip)

    # ------------------------------------------------------------------
    # Waterplane contour at a given height (returns y-coords per station)
    # ------------------------------------------------------------------

    def waterplane(self, z: float) -> np.ndarray:
        """Half-breadths along the waterplane at height z (one value per station)."""
        return self.half_breadths_at(z)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "ship_name"    : self.name,
            "stations"     : self.stations.tolist(),
            "waterlines"   : self.waterlines.tolist(),
            "half_breadths": self.half_breadths.tolist(),
            "rho"          : self.rho,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Hull":
        return cls(
            stations      = np.asarray(d["stations"],      float),
            waterlines    = np.asarray(d["waterlines"],    float),
            half_breadths = np.asarray(d["half_breadths"], float),
            name          = d.get("ship_name", "Ship"),
            rho           = float(d.get("rho", 1.025)),
        )
