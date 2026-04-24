"""
Interactive 3-D hull visualisation with Plotly
==============================================

Generates a watertight surface mesh from the offset table and overlays a
semi-transparent waterplane that can be tilted by heel and trim.

Uses only plotly.graph_objects – no plotly-express – so the mesh can be
embedded directly in Streamlit or exported as a standalone HTML file.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .hull import Hull


# ---------------------------------------------------------------------------

def _hull_surface(hull: Hull):
    """
    Build two Surface traces: port (y < 0) and starboard (y > 0).  The
    coordinate system is (x along length, y athwartship, z up).
    """
    X, Y, Z = np.meshgrid(hull.stations, [0], hull.waterlines, indexing="ij")
    # Starboard half-breadths (positive y)
    y_sb = hull.half_breadths           # [n_sta × n_wl]
    y_pt = -hull.half_breadths          # port side (mirrored)

    xs = np.repeat(hull.stations[:, None], len(hull.waterlines), axis=1)
    zs = np.repeat(hull.waterlines[None, :], len(hull.stations), axis=0)

    sb = go.Surface(
        x=xs, y=y_sb, z=zs,
        colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
        opacity=0.92, showscale=False, name="Starboard",
        lighting=dict(ambient=0.55, diffuse=0.75, specular=0.18, roughness=0.5),
        hoverinfo="skip",
    )
    pt = go.Surface(
        x=xs, y=y_pt, z=zs,
        colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
        opacity=0.92, showscale=False, name="Port",
        lighting=dict(ambient=0.55, diffuse=0.75, specular=0.18, roughness=0.5),
        hoverinfo="skip",
    )
    return sb, pt


def _waterplane_trace(hull: Hull, draft: float, heel_deg: float = 0.0,
                      trim_m: float = 0.0):
    """Semi-transparent plane representing the (possibly heeled/trimmed) waterline."""
    phi  = np.radians(heel_deg)
    x    = np.array([hull.stations[0], hull.stations[-1]])
    y    = np.array([-hull.B_max * 1.3, hull.B_max * 1.3])
    X, Y = np.meshgrid(x, y)
    # z(x,y) = draft + trim_slope · (x − x_mid) − y · tan(φ)
    x_mid = 0.5 * (hull.stations[0] + hull.stations[-1])
    slope = trim_m / hull.L
    Z = draft + slope * (X - x_mid) - Y * np.tan(phi)
    return go.Surface(
        x=X, y=Y, z=Z,
        colorscale=[(0.0, "#b3d9ff"), (1.0, "#4da6ff")],
        opacity=0.35, showscale=False, name="Waterline",
        lighting=dict(ambient=0.8, diffuse=0.4, specular=0.2),
        hoverinfo="skip",
    )


# ---------------------------------------------------------------------------

def hull_3d_figure(
    hull       : Hull,
    draft      : float,
    heel_deg   : float = 0.0,
    trim_m     : float = 0.0,
    title      : str   = "",
) -> go.Figure:
    sb, pt = _hull_surface(hull)
    wp     = _waterplane_trace(hull, draft, heel_deg, trim_m)
    fig = go.Figure(data=[sb, pt, wp])
    fig.update_layout(
        title=title or hull.name,
        scene=dict(
            xaxis_title="x – length (m)",
            yaxis_title="y – breadth (m)",
            zaxis_title="z – height (m)",
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=1.3, z=1.1)),
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------

def save_html(fig: go.Figure, path: str) -> None:
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
