"""
Interactive 3-D hull visualisation with Plotly
==============================================

Cinematic, watertight Mesh3d hull rendering with antifouling/topside
shading, wavy translucent sea, glow point markers, and comet B-trail.
All public function signatures are preserved for `app.py`.

Coordinate system (body-fixed):
    x : along length (AP → FP)
    y : athwartship (+ stbd)
    z : up (keel = waterline 0)
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from .hull import Hull


# ---------------------------------------------------------------------------
# Studio palette + scene helpers
# ---------------------------------------------------------------------------

# Dark cinematic backdrop
_BG_PAPER = "#0a121b"
_BG_SCENE = "#101c2a"
_GRID     = "#2a3a4d"
_AXIS_TXT = "#9fb1c4"

# Hull colorscale parameterized on **signed distance below waterline**
# negative → above WL (white / cool grey topside)
# zero      → boot-top stripe (red ochre)
# positive → antifouling red
_HULL_COLORSCALE = [
    (0.00, "#dfe6ee"),   # high freeboard / deck — cool light grey
    (0.42, "#fafafa"),   # topside white
    (0.49, "#d3a89e"),   # boot-top transition
    (0.50, "#9b2a25"),   # boot-top crisp red
    (0.52, "#7a1e1c"),   # antifouling red
    (1.00, "#3f0d0c"),   # deep keel red-black
]

_SEA_COLORSCALE = [
    (0.00, "#04263d"),   # trough deep navy
    (0.50, "#0f5fa0"),   # mid blue
    (1.00, "#7ad0ff"),   # crest sky-blue
]


def _scene_layout(camera_eye=(1.6, -1.4, 0.9), aspect="data") -> dict:
    return dict(
        bgcolor=_BG_SCENE,
        xaxis=dict(
            title=dict(text="x – length (m)", font=dict(color=_AXIS_TXT)),
            backgroundcolor=_BG_SCENE, gridcolor=_GRID,
            zerolinecolor="#3d5067", tickfont=dict(color=_AXIS_TXT),
            showspikes=False,
        ),
        yaxis=dict(
            title=dict(text="y – breadth (m)", font=dict(color=_AXIS_TXT)),
            backgroundcolor=_BG_SCENE, gridcolor=_GRID,
            zerolinecolor="#3d5067", tickfont=dict(color=_AXIS_TXT),
            showspikes=False,
        ),
        zaxis=dict(
            title=dict(text="z – height (m)", font=dict(color=_AXIS_TXT)),
            backgroundcolor=_BG_SCENE, gridcolor=_GRID,
            zerolinecolor="#3d5067", tickfont=dict(color=_AXIS_TXT),
            showspikes=False,
        ),
        aspectmode=aspect,
        camera=dict(
            eye=dict(x=camera_eye[0], y=camera_eye[1], z=camera_eye[2]),
            up=dict(x=0, y=0, z=1),
            projection=dict(type="perspective"),
        ),
    )


def _base_layout(title: str, camera_eye=(1.6, -1.4, 0.9), aspect="data") -> dict:
    return dict(
        title=dict(text=title, font=dict(color="#e6edf5", size=16),
                   x=0.02, xanchor="left"),
        paper_bgcolor=_BG_PAPER,
        plot_bgcolor=_BG_PAPER,
        font=dict(color="#cfd8e3"),
        scene=_scene_layout(camera_eye, aspect),
        margin=dict(l=0, r=0, t=46, b=0),
        legend=dict(bgcolor="rgba(15,25,40,0.6)", font=dict(color="#cfd8e3"),
                    bordercolor="#2a3a4d", borderwidth=1),
    )


# Rotation helper shared across functions
def _rot(y_b, z_b, phi_deg: float):
    """Body → earth: y_e = y·cosφ + z·sinφ,  z_e = −y·sinφ + z·cosφ"""
    phi = np.radians(phi_deg)
    cp, sp = np.cos(phi), np.sin(phi)
    return y_b * cp + z_b * sp, -y_b * sp + z_b * cp


# ---------------------------------------------------------------------------
# Watertight hull mesh (Mesh3d)
# ---------------------------------------------------------------------------

def _build_hull_topology(hull: Hull):
    """
    Build the static body-fixed vertex/face topology of a watertight hull
    composed of:
        • starboard skin       (n_sta × n_wl quads → triangles)
        • port skin            (mirror)
        • flat keel strip      (sb keel ↔ pt keel)
        • flat deck strip      (sb deck ↔ pt deck)
        • bow + stern caps     (fan triangulation)

    Returns
    -------
    verts_body : (N, 3) float array
    faces      : (M, 3) int array  (vertex indices per triangle)
    """
    sta = np.asarray(hull.stations,  dtype=float)
    wl  = np.asarray(hull.waterlines, dtype=float)
    hb  = np.asarray(hull.half_breadths, dtype=float)
    n_s, n_w = len(sta), len(wl)

    verts: list[tuple[float, float, float]] = []
    sb_idx = np.zeros((n_s, n_w), dtype=np.int32)
    pt_idx = np.zeros((n_s, n_w), dtype=np.int32)

    for i in range(n_s):
        for j in range(n_w):
            sb_idx[i, j] = len(verts)
            verts.append((sta[i],  hb[i, j], wl[j]))
    for i in range(n_s):
        for j in range(n_w):
            pt_idx[i, j] = len(verts)
            verts.append((sta[i], -hb[i, j], wl[j]))

    faces: list[tuple[int, int, int]] = []

    # Side skins
    for side, idx in (("sb", sb_idx), ("pt", pt_idx)):
        for i in range(n_s - 1):
            for j in range(n_w - 1):
                a = int(idx[i,     j    ])
                b = int(idx[i + 1, j    ])
                c = int(idx[i + 1, j + 1])
                d = int(idx[i,     j + 1])
                if side == "sb":   # outward normal +y / +z mix
                    faces.append((a, b, c)); faces.append((a, c, d))
                else:              # flipped winding for outward normal
                    faces.append((a, c, b)); faces.append((a, d, c))

    # Keel strip (j=0): sb[i,0] — pt[i,0]
    for i in range(n_s - 1):
        a = int(sb_idx[i,     0]); b = int(pt_idx[i,     0])
        c = int(pt_idx[i + 1, 0]); d = int(sb_idx[i + 1, 0])
        faces.append((a, b, c)); faces.append((a, c, d))

    # Deck strip (j=-1)
    j_top = n_w - 1
    for i in range(n_s - 1):
        a = int(sb_idx[i,     j_top]); b = int(sb_idx[i + 1, j_top])
        c = int(pt_idx[i + 1, j_top]); d = int(pt_idx[i,     j_top])
        faces.append((a, b, c)); faces.append((a, c, d))

    # Bow/stern caps via fan triangulation of the closed station polygon
    for i_end in (0, n_s - 1):
        poly = [int(sb_idx[i_end, j]) for j in range(n_w)]
        poly += [int(pt_idx[i_end, j]) for j in range(n_w - 1, -1, -1)]
        for k in range(1, len(poly) - 1):
            tri = (poly[0], poly[k], poly[k + 1])
            # winding flip on stern so normals point outward
            if i_end == 0:
                faces.append((tri[0], tri[2], tri[1]))
            else:
                faces.append(tri)

    return np.asarray(verts, dtype=float), np.asarray(faces, dtype=np.int32)


def _hull_mesh3d(
    hull          : Hull,
    draft         : float,
    heel_deg      : float = 0.0,
    name          : str   = "Hull",
    show_legend   : bool  = True,
) -> go.Mesh3d:
    """
    Watertight mesh with antifouling/topside coloring driven by signed
    distance below the heeled waterline (sea is flat in earth frame).
    """
    verts, faces = _build_hull_topology(hull)
    y_e, z_e = _rot(verts[:, 1], verts[:, 2], heel_deg)
    x_e = verts[:, 0]

    submerge = draft - z_e            # +ve below WL → antifouling red
    z_max = float(np.max(verts[:, 2]))
    z_min = float(np.min(verts[:, 2]))
    span = max(draft - z_min, z_max - draft, 1e-3)

    return go.Mesh3d(
        x=x_e, y=y_e, z=z_e,
        i=faces[:, 0], j=faces[:, 1], k=faces[:, 2],
        intensity=submerge,
        cmin=-span, cmax=+span, cmid=0.0,
        colorscale=_HULL_COLORSCALE,
        showscale=False,
        flatshading=False,
        opacity=1.0,
        name=name,
        showlegend=show_legend,
        lighting=dict(
            ambient=0.32, diffuse=0.95, specular=0.45,
            roughness=0.32, fresnel=0.25,
        ),
        lightposition=dict(x=200, y=200, z=350),
        hoverinfo="skip",
    )


# ---------------------------------------------------------------------------
# Animated wavy sea
# ---------------------------------------------------------------------------

def _sea_surface(
    hull       : Hull,
    draft      : float,
    n          : int   = 70,
    amp        : float = 0.0,
    phase      : float = 0.0,
    span_pad_x : float = 0.35,
    span_pad_y : float = 1.6,
    name       : str   = "Sea",
) -> go.Surface:
    L  = float(hull.L)
    Bm = float(hull.B_max)
    x0 = float(hull.stations[0])  - span_pad_x * L
    x1 = float(hull.stations[-1]) + span_pad_x * L
    y0 = -span_pad_y * Bm - 0.5 * Bm
    y1 = +span_pad_y * Bm + 0.5 * Bm
    xv = np.linspace(x0, x1, n)
    yv = np.linspace(y0, y1, n)
    X, Y = np.meshgrid(xv, yv)
    if amp > 0.0:
        kx = 2.0 * np.pi / max(0.4 * L, 1.0)
        ky = 2.0 * np.pi / max(0.6 * Bm, 1.0)
        Z  = draft + amp * (np.sin(kx * X + phase)
                            + 0.55 * np.sin(ky * Y + 0.7 * phase))
    else:
        Z = np.full_like(X, draft)
    return go.Surface(
        x=X, y=Y, z=Z,
        surfacecolor=Z,
        colorscale=_SEA_COLORSCALE,
        cmin=draft - max(amp, 0.4),
        cmax=draft + max(amp, 0.4),
        opacity=0.62,
        showscale=False,
        lighting=dict(
            ambient=0.35, diffuse=0.55, specular=0.85,
            roughness=0.12, fresnel=0.7,
        ),
        lightposition=dict(x=400, y=400, z=600),
        contours=dict(z=dict(show=False)),
        hoverinfo="skip",
        name=name,
    )


def _sea_floor(hull: Hull, draft: float) -> go.Surface:
    """Dark seafloor backdrop a few hull-depths below the waterline."""
    L  = float(hull.L);  Bm = float(hull.B_max);  D = float(hull.D)
    x0 = float(hull.stations[0]) - 0.4 * L
    x1 = float(hull.stations[-1]) + 0.4 * L
    y0, y1 = -2.5 * Bm, 2.5 * Bm
    X, Y = np.meshgrid([x0, x1], [y0, y1])
    Z = np.full_like(X, draft - max(2.0 * D, 4.0))
    return go.Surface(
        x=X, y=Y, z=Z,
        colorscale=[(0, "#040b14"), (1, "#06182b")],
        showscale=False, opacity=1.0,
        lighting=dict(ambient=0.7, diffuse=0.2, specular=0.0),
        hoverinfo="skip", name="Seafloor", showlegend=False,
    )


# ---------------------------------------------------------------------------
# Glow point marker (halo + core)
# ---------------------------------------------------------------------------

def _glow_marker(x, y, z, label: str, color: str, size: int = 9):
    halo = go.Scatter3d(
        x=[x], y=[y], z=[z], mode="markers",
        marker=dict(size=size * 2.6, color=color, opacity=0.18,
                    line=dict(width=0)),
        showlegend=False, hoverinfo="skip",
    )
    ring = go.Scatter3d(
        x=[x], y=[y], z=[z], mode="markers",
        marker=dict(size=size * 1.7, color=color, opacity=0.45,
                    line=dict(width=0)),
        showlegend=False, hoverinfo="skip",
    )
    core = go.Scatter3d(
        x=[x], y=[y], z=[z], mode="markers+text",
        text=[f"<b>{label}</b>"], textposition="top center",
        textfont=dict(size=14, color="#f5f9ff"),
        marker=dict(size=size, color=color,
                    line=dict(color="#ffffff", width=2)),
        name=label,
    )
    return [halo, ring, core]


# ---------------------------------------------------------------------------
# Backwards-compat: split surface helper still used elsewhere
# ---------------------------------------------------------------------------

def _hull_surface(hull: Hull):
    """Legacy two-Surface split.  Retained so any external caller still works."""
    xs = np.repeat(hull.stations[:, None], len(hull.waterlines), axis=1)
    zs = np.repeat(hull.waterlines[None, :], len(hull.stations), axis=0)
    sb = go.Surface(
        x=xs, y=hull.half_breadths, z=zs,
        colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
        opacity=0.92, showscale=False, name="Starboard",
        lighting=dict(ambient=0.55, diffuse=0.75, specular=0.18, roughness=0.5),
        hoverinfo="skip",
    )
    pt = go.Surface(
        x=xs, y=-hull.half_breadths, z=zs,
        colorscale=[(0.0, "#bbd4ea"), (1.0, "#1f6aa5")],
        opacity=0.92, showscale=False, name="Port",
        lighting=dict(ambient=0.55, diffuse=0.75, specular=0.18, roughness=0.5),
        hoverinfo="skip",
    )
    return sb, pt


def _waterplane_trace(hull: Hull, draft: float, heel_deg: float = 0.0,
                      trim_m: float = 0.0):
    """Heeled / trimmed translucent waterplane (kept for callers needing it)."""
    phi  = np.radians(heel_deg)
    x    = np.array([hull.stations[0], hull.stations[-1]])
    y    = np.array([-hull.B_max * 1.3, hull.B_max * 1.3])
    X, Y = np.meshgrid(x, y)
    x_mid = 0.5 * (hull.stations[0] + hull.stations[-1])
    slope = trim_m / hull.L
    Z = draft + slope * (X - x_mid) - Y * np.tan(phi)
    return go.Surface(
        x=X, y=Y, z=Z,
        colorscale=[(0.0, "#0e3b66"), (1.0, "#3aa1ff")],
        opacity=0.42, showscale=False, name="Waterline",
        lighting=dict(ambient=0.5, diffuse=0.5, specular=0.6, roughness=0.1),
        hoverinfo="skip",
    )


# ---------------------------------------------------------------------------
# Static hull figure
# ---------------------------------------------------------------------------

def hull_3d_figure(
    hull       : Hull,
    draft      : float,
    heel_deg   : float = 0.0,
    trim_m     : float = 0.0,
    title      : str   = "",
) -> go.Figure:
    fig = go.Figure(data=[
        _sea_floor(hull, draft),
        _hull_mesh3d(hull, draft, heel_deg=heel_deg, name="Hull"),
        _sea_surface(hull, draft, amp=0.18),
    ])
    fig.update_layout(_base_layout(title or hull.name,
                                   camera_eye=(1.5, -1.3, 0.95)))
    return fig


# ---------------------------------------------------------------------------

def save_html(fig: go.Figure, path: str) -> None:
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)


# ---------------------------------------------------------------------------
# Animated rolling-ship figure (capsize simulator)
# ---------------------------------------------------------------------------

def hull_3d_rolling_animation(
    hull      : Hull,
    draft     : float,
    phi_deg_t : np.ndarray,
    t_s       : np.ndarray,
    n_frames  : int = 60,
    title     : str = "",
) -> go.Figure:
    """
    Cinematic rolling animation: watertight Mesh3d hull rotates in earth
    frame; flat sea with subtle wave; sea-floor backdrop.
    """
    phi_deg_t = np.asarray(phi_deg_t, dtype=float)
    t_s       = np.asarray(t_s,       dtype=float)
    if len(phi_deg_t) > n_frames:
        idx = np.linspace(0, len(phi_deg_t) - 1, n_frames).astype(int)
    else:
        idx = np.arange(len(phi_deg_t))
    phi_frames = phi_deg_t[idx]
    t_frames   = t_s[idx]

    sea_floor = _sea_floor(hull, draft)

    def _frame_data(phi_deg: float, k: int):
        phase = 0.4 * k
        return [
            sea_floor,
            _hull_mesh3d(hull, draft, heel_deg=phi_deg,
                         name="Hull", show_legend=(k == 0)),
            _sea_surface(hull, draft, amp=0.18, phase=phase),
        ]

    frames = [
        go.Frame(
            data=_frame_data(phi, k),
            name=f"{t:.1f}",
            layout=go.Layout(
                title=dict(
                    text=f"{title or hull.name}  ·  t = {t:.1f} s  ·  φ = {phi:+.1f}°",
                    font=dict(color="#e6edf5", size=16),
                    x=0.02, xanchor="left",
                )
            ),
        )
        for k, (phi, t) in enumerate(zip(phi_frames, t_frames))
    ]

    fig = go.Figure(
        data=_frame_data(phi_frames[0], 0),
        layout=go.Layout(
            **_base_layout(
                f"{title or hull.name}  ·  t = {t_frames[0]:.1f} s  ·  φ = {phi_frames[0]:+.1f}°",
                camera_eye=(0.4, -2.4, 0.7),
            ),
            updatemenus=[_play_pause_buttons(60)],
            sliders=[_make_slider(frames, prefix="t = ", suffix=" s")],
        ),
        frames=frames,
    )
    return fig


# ---------------------------------------------------------------------------
# Static hull with B / G / M markers
# ---------------------------------------------------------------------------

def hull_3d_with_points(
    hull    : Hull,
    draft   : float,
    KG      : float,
    heel_deg: float = 0.0,
) -> go.Figure:
    from .hydrostatics import Hydrostatics
    from .heeled import HeeledHydrostatics

    hs    = Hydrostatics(hull, draft, KG)
    KM    = float(hs.KM)
    x_mid = float(np.mean(hull.stations))

    if abs(heel_deg) < 0.1:
        x_B, y_B, z_B = x_mid, 0.0, float(hs.KB)
    else:
        V0 = hs.displacement_volume
        hh = HeeledHydrostatics(hull, heel_deg, V0, KG, draft)
        x_B, y_B, z_B = hh.B_body

    y_B_e, z_B_e = _rot(np.array([y_B]),  np.array([z_B]),  heel_deg)
    y_G_e, z_G_e = _rot(np.array([0.0]),  np.array([KG]),   heel_deg)
    y_M_e, z_M_e = _rot(np.array([0.0]),  np.array([KM]),   heel_deg)

    traces = [
        _sea_floor(hull, draft),
        _hull_mesh3d(hull, draft, heel_deg=heel_deg, name="Hull"),
        _sea_surface(hull, draft, amp=0.15),
    ]

    traces += _glow_marker(x_B,   float(y_B_e[0]), float(z_B_e[0]), "B", "#3aa1ff")
    traces += _glow_marker(x_mid, float(y_G_e[0]), float(z_G_e[0]), "G", "#ff5252")
    traces += _glow_marker(x_mid, float(y_M_e[0]), float(z_M_e[0]), "M", "#ffb13a")

    # BG / GM arms
    traces.append(go.Scatter3d(
        x=[x_mid, x_B], y=[float(y_G_e[0]), float(y_B_e[0])],
        z=[float(z_G_e[0]), float(z_B_e[0])],
        mode="lines", line=dict(color="#9aa6b3", width=4, dash="dot"),
        name="BG", showlegend=False, hoverinfo="skip",
    ))
    traces.append(go.Scatter3d(
        x=[x_mid, x_mid], y=[float(y_G_e[0]), float(y_M_e[0])],
        z=[float(z_G_e[0]), float(z_M_e[0])],
        mode="lines", line=dict(color="#ffb13a", width=5, dash="dash"),
        name="GM", showlegend=False, hoverinfo="skip",
    ))

    fig = go.Figure(data=traces)
    fig.update_layout(_base_layout(
        f"{hull.name}  |  φ={heel_deg:.1f}°  KG={KG:.2f} m  GM={hs.GM:.3f} m",
        camera_eye=(0.6, -2.2, 0.9),
    ))
    return fig


# ---------------------------------------------------------------------------
# Heel sweep animation with comet B-trail
# ---------------------------------------------------------------------------

def hull_3d_heel_sweep_animation(
    hull      : Hull,
    draft     : float,
    KG        : float,
    angles_deg: np.ndarray | None = None,
) -> go.Figure:
    from .hydrostatics import Hydrostatics
    from .heeled import HeeledHydrostatics

    if angles_deg is None:
        angles_deg = np.arange(0, 61, 5, dtype=float)
    angles_deg = np.asarray(angles_deg, dtype=float)

    hs    = Hydrostatics(hull, draft, KG)
    V0    = hs.displacement_volume
    KM    = float(hs.KM)
    x_mid = float(np.mean(hull.stations))

    # Pre-compute B(φ) in earth frame
    B_earth: list[tuple[float, float]] = []
    for phi in angles_deg:
        if abs(phi) < 0.1:
            y_B, z_B = 0.0, float(hs.KB)
        else:
            hh = HeeledHydrostatics(hull, phi, V0, KG, draft)
            _, y_B, z_B = hh.B_body
        ye, ze = _rot(np.array([y_B]), np.array([z_B]), phi)
        B_earth.append((float(ye[0]), float(ze[0])))

    sea_floor = _sea_floor(hull, draft)

    def _frame_traces(i: int):
        phi = float(angles_deg[i])
        bx, bz = B_earth[i]
        gy_e, gz_e = _rot(np.array([0.0]), np.array([KG]), phi)
        my_e, mz_e = _rot(np.array([0.0]), np.array([KM]), phi)

        # Comet trail with brightness gradient
        trail_x = [x_mid] * (i + 1)
        trail_y = [B_earth[j][0] for j in range(i + 1)]
        trail_z = [B_earth[j][1] for j in range(i + 1)]
        trail_intensity = list(range(i + 1))

        out = [
            sea_floor,
            _hull_mesh3d(hull, draft, heel_deg=phi, name="Hull",
                         show_legend=(i == 0)),
            _sea_surface(hull, draft, amp=0.16, phase=0.3 * i),
            go.Scatter3d(
                x=trail_x, y=trail_y, z=trail_z,
                mode="lines",
                line=dict(color=trail_intensity, colorscale="Blues",
                          width=6, cmin=0, cmax=max(1, len(angles_deg) - 1)),
                name="B path", hoverinfo="skip",
                showlegend=(i == 0),
            ),
        ]
        out += _glow_marker(x_mid, bx, bz, "B", "#3aa1ff", size=10)
        out += _glow_marker(x_mid, float(gy_e[0]), float(gz_e[0]), "G", "#ff5252", size=10)
        out += _glow_marker(x_mid, float(my_e[0]), float(mz_e[0]), "M", "#ffb13a", size=9)

        # GZ arm (earth-horizontal from G to projected B at G's height)
        out.append(go.Scatter3d(
            x=[x_mid, x_mid],
            y=[float(gy_e[0]), bx],
            z=[float(gz_e[0]), float(gz_e[0])],
            mode="lines",
            line=dict(color="#5cdb5c", width=6, dash="dash"),
            name="GZ arm", hoverinfo="skip", showlegend=(i == 0),
        ))
        return out

    frames = [
        go.Frame(
            data=_frame_traces(i),
            name=f"{angles_deg[i]:.0f}",
            layout=go.Layout(
                title=dict(
                    text=f"{hull.name}  ·  φ = {angles_deg[i]:+.1f}°",
                    font=dict(color="#e6edf5", size=16),
                    x=0.02, xanchor="left",
                )
            ),
        )
        for i in range(len(angles_deg))
    ]

    fig = go.Figure(
        data=_frame_traces(0),
        layout=go.Layout(
            **_base_layout(
                f"{hull.name}  ·  Heel sweep φ=0°",
                camera_eye=(0.4, -2.4, 0.7),
            ),
            updatemenus=[_play_pause_buttons(280, transition_ms=120)],
            sliders=[_make_slider(frames, prefix="φ = ", suffix="°")],
        ),
        frames=frames,
    )
    return fig


# ---------------------------------------------------------------------------
# Draft rise animation (waterplane rises through hull)
# ---------------------------------------------------------------------------

def hull_3d_draft_animation(
    hull    : Hull,
    KG      : float,
    T_max   : float | None = None,
    n_frames: int = 40,
) -> go.Figure:
    if T_max is None:
        T_max = hull.D * 0.9

    drafts = np.linspace(hull.D * 0.05, T_max, n_frames)

    def _frame_data(draft: float, k: int):
        return [
            _sea_floor(hull, draft),
            _hull_mesh3d(hull, draft, heel_deg=0.0,
                         name="Hull", show_legend=(k == 0)),
            _sea_surface(hull, draft, amp=0.14, phase=0.4 * k),
        ]

    frames = [
        go.Frame(
            data=_frame_data(d, k),
            name=f"{d:.2f}",
            layout=go.Layout(
                title=dict(
                    text=f"{hull.name}  ·  T = {d:.2f} m",
                    font=dict(color="#e6edf5", size=16),
                    x=0.02, xanchor="left",
                )
            ),
        )
        for k, d in enumerate(drafts)
    ]

    fig = go.Figure(
        data=_frame_data(drafts[0], 0),
        layout=go.Layout(
            **_base_layout(
                f"{hull.name}  ·  Draft animation",
                camera_eye=(1.5, -1.5, 1.0),
            ),
            updatemenus=[_play_pause_buttons(80)],
            sliders=[_make_slider(frames, prefix="T = ", suffix=" m")],
        ),
        frames=frames,
    )
    return fig


# ---------------------------------------------------------------------------
# GZ surface : GZ(heel, draft)
# ---------------------------------------------------------------------------

def gz_surface_3d(
    hull        : Hull,
    KG          : float,
    draft_range : tuple[float, float] | None = None,
    heel_range  : tuple[float, float] = (0.0, 70.0),
    n_drafts    : int = 8,
    n_heels     : int = 10,
    design_draft: float | None = None,
) -> go.Figure:
    """
    Cinematic GZ(φ, T) surface with diverging colorscale, projected
    isocontours on the floor, GZ=0 capsize ribbon, and the design-draft
    slice highlighted as a glowing track.
    """
    from .heeled import gz_curve_true

    if draft_range is None:
        draft_range = (hull.D * 0.3, hull.D * 0.9)

    drafts = np.linspace(draft_range[0], draft_range[1], n_drafts)
    heels  = np.linspace(heel_range[0],  heel_range[1],  n_heels)

    GZ = np.zeros((n_heels, n_drafts))
    for j, T in enumerate(drafts):
        try:
            _, gz = gz_curve_true(hull, T, KG, angles_deg=heels)
            GZ[:, j] = gz
        except Exception:
            GZ[:, j] = np.nan

    HEELS, DRAFTS = np.meshgrid(heels, drafts, indexing="ij")
    z_lo = float(np.nanmin(GZ))
    z_hi = float(np.nanmax(GZ))

    surf = go.Surface(
        x=HEELS, y=DRAFTS, z=GZ,
        colorscale=[
            (0.00, "#7a0d0a"), (0.30, "#d62728"),
            (0.49, "#ffb6b3"),
            (0.50, "#f5f5f5"),
            (0.51, "#aec7e8"),
            (0.70, "#1f77b4"), (1.00, "#0a3d6b"),
        ],
        cmid=0.0,
        opacity=0.95, showscale=True,
        colorbar=dict(title=dict(text="GZ (m)", font=dict(color=_AXIS_TXT)),
                      tickfont=dict(color=_AXIS_TXT),
                      len=0.6, thickness=14, x=0.95),
        contours=dict(
            z=dict(show=True, project_z=True, usecolormap=True,
                   highlightcolor="#ffffff", width=2),
            x=dict(show=False), y=dict(show=False),
        ),
        lighting=dict(ambient=0.35, diffuse=0.85, specular=0.4,
                      roughness=0.3, fresnel=0.2),
        lightposition=dict(x=200, y=200, z=400),
        name="GZ surface", showlegend=True,
        hovertemplate=("φ = %{x:.1f}°<br>T = %{y:.2f} m<br>"
                       "GZ = %{z:.3f} m<extra></extra>"),
    )

    traces: list = [surf]

    # Translucent capsize plane at GZ=0
    traces.append(go.Surface(
        x=np.array([[heel_range[0], heel_range[1]],
                    [heel_range[0], heel_range[1]]]),
        y=np.array([[draft_range[0], draft_range[0]],
                    [draft_range[1], draft_range[1]]]),
        z=np.zeros((2, 2)),
        colorscale=[(0, "rgba(214, 39, 40, 0.18)"),
                    (1, "rgba(214, 39, 40, 0.18)")],
        showscale=False, opacity=0.38,
        lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
        name="GZ = 0", hoverinfo="skip", showlegend=True,
    ))

    # Design draft slice as glow track
    if design_draft is not None:
        _, gz_des = gz_curve_true(hull, design_draft, KG, angles_deg=heels)
        traces.append(go.Scatter3d(
            x=heels, y=np.full_like(heels, design_draft), z=gz_des,
            mode="lines+markers",
            line=dict(color="#ffb13a", width=8),
            marker=dict(size=6, color="#ffb13a",
                        line=dict(color="#fff7e0", width=1)),
            name=f"Design T = {design_draft:.1f} m",
            hovertemplate=("φ = %{x:.1f}°<br>"
                           "GZ = %{z:.3f} m<extra></extra>"),
        ))
        # halo trace beneath
        traces.append(go.Scatter3d(
            x=heels, y=np.full_like(heels, design_draft), z=gz_des,
            mode="lines",
            line=dict(color="rgba(255,177,58,0.25)", width=18),
            showlegend=False, hoverinfo="skip",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(text=f"GZ surface — {hull.name}  (KG = {KG:.2f} m)",
                   font=dict(color="#e6edf5", size=16),
                   x=0.02, xanchor="left"),
        paper_bgcolor=_BG_PAPER, plot_bgcolor=_BG_PAPER,
        font=dict(color="#cfd8e3"),
        scene=dict(
            xaxis=dict(title=dict(text="φ (°)", font=dict(color=_AXIS_TXT)),
                       backgroundcolor=_BG_SCENE, gridcolor=_GRID,
                       tickfont=dict(color=_AXIS_TXT)),
            yaxis=dict(title=dict(text="Draft T (m)", font=dict(color=_AXIS_TXT)),
                       backgroundcolor=_BG_SCENE, gridcolor=_GRID,
                       tickfont=dict(color=_AXIS_TXT)),
            zaxis=dict(title=dict(text="GZ (m)", font=dict(color=_AXIS_TXT)),
                       backgroundcolor=_BG_SCENE, gridcolor=_GRID,
                       tickfont=dict(color=_AXIS_TXT)),
            aspectmode="manual",
            aspectratio=dict(x=1.5, y=1, z=0.7),
            camera=dict(eye=dict(x=1.6, y=-1.7, z=1.0),
                        up=dict(x=0, y=0, z=1)),
        ),
        margin=dict(l=0, r=0, t=46, b=0),
        legend=dict(bgcolor="rgba(15,25,40,0.6)", font=dict(color="#cfd8e3"),
                    bordercolor="#2a3a4d", borderwidth=1),
    )
    return fig


# ---------------------------------------------------------------------------
# Station cross-section
# ---------------------------------------------------------------------------

def station_cross_section_figure(
    hull        : Hull,
    draft       : float,
    heel_angles : list[float] | None = None,
    station_frac: float = 0.5,
) -> go.Figure:
    """
    2-D cross-section at the station closest to `station_frac · L`
    rendered on the dark studio backdrop with antifouling fill.
    """
    if heel_angles is None:
        heel_angles = [0, 15, 30, 45]

    x_target = hull.stations[0] + station_frac * (hull.stations[-1] - hull.stations[0])
    sta_idx  = int(np.argmin(np.abs(np.asarray(hull.stations) - x_target)))
    x_sta    = hull.stations[sta_idx]

    wl = np.asarray(hull.waterlines)
    hb = hull.half_breadths[sta_idx]
    y_outline = np.concatenate([-hb[::-1], hb, [-hb[-1]]])
    z_outline = np.concatenate([wl[::-1],  wl, [wl[-1]]])

    traces = [
        go.Scatter(
            x=y_outline, y=z_outline, mode="lines",
            line=dict(color="#dfe6ee", width=2.5),
            fill="toself", fillcolor="rgba(122,30,28,0.28)",
            name="Hull outline",
            hovertemplate="y = %{x:.2f} m<br>z = %{y:.2f} m<extra></extra>",
        ),
    ]

    palette = ["#3aa1ff", "#ffb13a", "#5cdb5c", "#ff5252",
               "#b97aff", "#f78fb3", "#7f7f7f", "#00d4d4"]

    for k, phi in enumerate(heel_angles):
        col = palette[k % len(palette)]
        phi_r = np.radians(phi)
        y_wl = np.array([-hull.B_max * 1.4, hull.B_max * 1.4])
        z_wl = draft - y_wl * np.tan(phi_r)
        traces.append(go.Scatter(
            x=y_wl, y=z_wl, mode="lines",
            line=dict(color=col, width=2.2,
                      dash=("solid" if phi == 0 else "dash")),
            name=f"WL φ = {phi}°",
            hoverinfo="skip",
        ))

    # Submerged polygon shading at last heel
    try:
        phi_last = heel_angles[-1]
        sub = hull.submerged_section_heeled(sta_idx, draft, phi_last)
        if not sub.is_empty:
            geoms = [sub] if sub.geom_type == "Polygon" else list(sub.geoms)
            for k_g, g in enumerate(geoms):
                coords = list(g.exterior.coords)
                sy = [c[0] for c in coords]
                sz = [c[1] for c in coords]
                traces.append(go.Scatter(
                    x=sy, y=sz, mode="lines",
                    fill="toself",
                    fillcolor="rgba(58,161,255,0.32)",
                    line=dict(color="#3aa1ff", width=1.5),
                    name=(f"Submerged φ = {phi_last}°" if k_g == 0
                          else f"Submerged φ = {phi_last}° (#{k_g+1})"),
                    showlegend=(k_g == 0),
                    hoverinfo="skip",
                ))
    except Exception:
        pass

    # Waterline horizon shading at φ=0 for visual cue
    y_full = np.array([-hull.B_max * 1.4, -hull.B_max * 1.4,
                        hull.B_max * 1.4,  hull.B_max * 1.4])
    z_full = np.array([draft, wl[0] - 0.5, wl[0] - 0.5, draft])
    traces.insert(0, go.Scatter(
        x=y_full, y=z_full, mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0),
        fill="toself", fillcolor="rgba(15, 95, 160, 0.18)",
        showlegend=False, hoverinfo="skip", name="Sea",
    ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(text=f"Station cross-section  ·  x = {x_sta:.1f} m  "
                        f"({station_frac*100:.0f} % L)",
                   font=dict(color="#e6edf5", size=16),
                   x=0.02, xanchor="left"),
        paper_bgcolor=_BG_PAPER, plot_bgcolor=_BG_SCENE,
        font=dict(color="#cfd8e3"),
        xaxis=dict(title=dict(text="y – athwartship (m, +stbd)",
                              font=dict(color=_AXIS_TXT)),
                   gridcolor=_GRID, zerolinecolor="#445566",
                   tickfont=dict(color=_AXIS_TXT), scaleanchor="y"),
        yaxis=dict(title=dict(text="z – height (m)",
                              font=dict(color=_AXIS_TXT)),
                   gridcolor=_GRID, zerolinecolor="#445566",
                   tickfont=dict(color=_AXIS_TXT)),
        height=520,
        legend=dict(bgcolor="rgba(15,25,40,0.6)", font=dict(color="#cfd8e3"),
                    bordercolor="#2a3a4d", borderwidth=1, x=1.01, y=1),
    )
    return fig


# ---------------------------------------------------------------------------
# Internal: animation control widgets
# ---------------------------------------------------------------------------

def _play_pause_buttons(duration_ms: int = 80, transition_ms: int = 0) -> dict:
    return dict(
        type="buttons", showactive=False,
        bgcolor="#1c2a38", bordercolor="#2a3a4d",
        font=dict(color="#cfd8e3"),
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[None, dict(frame=dict(duration=duration_ms, redraw=True),
                                  fromcurrent=True,
                                  transition=dict(duration=transition_ms))]),
            dict(label="❚❚ Pause", method="animate",
                 args=[[None], dict(frame=dict(duration=0, redraw=False),
                                     mode="immediate")]),
        ],
        x=0.05, y=0.02, xanchor="left", yanchor="bottom",
    )


def _make_slider(frames, prefix: str = "", suffix: str = "") -> dict:
    return dict(
        active=0, x=0.15, y=0.02, len=0.78,
        bgcolor="#1c2a38",
        bordercolor="#2a3a4d",
        activebgcolor="#3aa1ff",
        font=dict(color="#cfd8e3"),
        currentvalue=dict(prefix=prefix, suffix=suffix, visible=True,
                          font=dict(color="#e6edf5")),
        steps=[dict(method="animate",
                    args=[[f.name], dict(mode="immediate",
                                         frame=dict(duration=0, redraw=True),
                                         transition=dict(duration=0))],
                    label=f.name)
               for f in frames],
    )
