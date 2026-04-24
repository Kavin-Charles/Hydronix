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


# ---------------------------------------------------------------------------
# Animated rolling-ship figure (for the capsize simulator)
# ---------------------------------------------------------------------------

def hull_3d_rolling_animation(
    hull      : Hull,
    draft     : float,
    phi_deg_t : np.ndarray,         # heel time series (°)
    t_s       : np.ndarray,         # corresponding time stamps (s)
    n_frames  : int = 60,
    title     : str = "",
) -> go.Figure:
    """
    Build a Plotly animation of the hull rolling in the earth frame.

    The body-fixed mesh is rotated about the longitudinal (x) axis by
    the heel angle φ(t).  The waterplane stays flat at z = draft in the
    earth frame.  This gives the viewer the 'ship tilting in calm water'
    experience — exactly what a spectator on the dock would see.
    """
    phi_deg_t = np.asarray(phi_deg_t, dtype=float)
    t_s       = np.asarray(t_s,       dtype=float)
    # Sub-sample to n_frames for performance
    if len(phi_deg_t) > n_frames:
        idx = np.linspace(0, len(phi_deg_t) - 1, n_frames).astype(int)
    else:
        idx = np.arange(len(phi_deg_t))
    phi_frames = phi_deg_t[idx]
    t_frames   = t_s[idx]

    # Body-frame mesh (same as _hull_surface but split into data)
    xs = np.repeat(hull.stations[:, None], len(hull.waterlines), axis=1)
    zs = np.repeat(hull.waterlines[None, :], len(hull.stations), axis=0)
    y_sb_body =  hull.half_breadths
    y_pt_body = -hull.half_breadths
    z_body    =  zs

    # Earth-frame waterplane (flat)
    wp_x = np.array([hull.stations[0], hull.stations[-1]])
    wp_y = np.array([-hull.B_max * 1.3, hull.B_max * 1.3])
    WPX, WPY = np.meshgrid(wp_x, wp_y)
    WPZ = np.full_like(WPX, draft, dtype=float)

    def _rotate(y_b: np.ndarray, z_b: np.ndarray, phi_deg: float):
        """Body → earth:  y_e = y·cosφ + z·sinφ,  z_e = −y·sinφ + z·cosφ."""
        phi = np.radians(phi_deg)
        cp, sp = np.cos(phi), np.sin(phi)
        return y_b * cp + z_b * sp, -y_b * sp + z_b * cp

    def _frame_data(phi_deg: float):
        y_sb_e, z_sb_e = _rotate(y_sb_body, z_body, phi_deg)
        y_pt_e, z_pt_e = _rotate(y_pt_body, z_body, phi_deg)
        sb = go.Surface(
            x=xs, y=y_sb_e, z=z_sb_e,
            colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
            opacity=0.95, showscale=False, name="Starboard",
            lighting=dict(ambient=0.55, diffuse=0.8, specular=0.2, roughness=0.5),
            hoverinfo="skip",
        )
        pt = go.Surface(
            x=xs, y=y_pt_e, z=z_pt_e,
            colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
            opacity=0.95, showscale=False, name="Port",
            lighting=dict(ambient=0.55, diffuse=0.8, specular=0.2, roughness=0.5),
            hoverinfo="skip",
        )
        wp = go.Surface(
            x=WPX, y=WPY, z=WPZ,
            colorscale=[(0.0, "#b3d9ff"), (1.0, "#4da6ff")],
            opacity=0.35, showscale=False, name="Waterline",
            lighting=dict(ambient=0.8, diffuse=0.4, specular=0.2),
            hoverinfo="skip",
        )
        return [sb, pt, wp]

    frames = [
        go.Frame(
            data=_frame_data(phi),
            name=f"{t:.1f}",
            layout=go.Layout(
                title=f"{title or hull.name} — t = {t:.1f} s, φ = {phi:+.1f}°",
            ),
        )
        for phi, t in zip(phi_frames, t_frames)
    ]

    fig = go.Figure(
        data=_frame_data(phi_frames[0]),
        layout=go.Layout(
            title=f"{title or hull.name} — t = {t_frames[0]:.1f} s, φ = {phi_frames[0]:+.1f}°",
            scene=dict(
                xaxis_title="x – length (m)",
                yaxis_title="y – earth breadth (m)",
                zaxis_title="z – earth height (m)",
                aspectmode="data",
                camera=dict(eye=dict(x=0.1, y=2.2, z=0.8)),  # view from astern
            ),
            margin=dict(l=0, r=0, t=40, b=0),
            template="plotly_white",
            updatemenus=[dict(
                type="buttons", showactive=False,
                buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=60, redraw=True),
                                          fromcurrent=True,
                                          transition=dict(duration=0))]),
                    dict(label="❚❚ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False),
                                             mode="immediate")]),
                ],
                x=0.05, y=0.02, xanchor="left", yanchor="bottom",
            )],
            sliders=[dict(
                active=0, x=0.15, y=0.02, len=0.8,
                currentvalue=dict(prefix="t = ", suffix=" s", visible=True),
                steps=[dict(method="animate",
                            args=[[f.name],
                                  dict(mode="immediate",
                                       frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))],
                            label=f.name)
                       for f in frames],
            )],
        ),
        frames=frames,
    )
    return fig
