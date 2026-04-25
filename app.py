"""
Hydronix — Streamlit Web UI
===========================

Interactive front-end for the first-principles hydrostatics & stability
suite.  Run with:

    streamlit run app.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from hydro.hull          import Hull
from hydro.hydrostatics  import Hydrostatics, hydrostatic_table
from hydro.heeled        import gz_curve_true, kn_curve_true, cross_curves_true
from hydro.stability     import gz_curve_wallsided, stability_parameters
from hydro.imo           import imo_intact_stability_check
from hydro.trim          import solve_equilibrium
from hydro.bonjean       import bonjean_curves
from hydro.free_surface  import fsm_rectangular_tank, gm_corrected
from hydro.weather       import weather_criterion
from hydro.io_formats    import load as load_hull_file, save_json
from hydro.benchmarks    import box_barge, wigley_hull, hackathon_ps_hull
from hydro                import plots, plots3d


# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Hydronix — Ship Hydrostatics",
    page_icon="assets/favicon.svg" if (Path(__file__).parent / "assets/favicon.svg").exists() else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Theme-aware design system (works in light + dark mode)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Inline SVG icon helper — no network deps, no font fallback to literal text.
# Paths sourced from Material Symbols (24×24 viewBox).  Uses currentColor so
# the surrounding CSS controls the colour.
# ---------------------------------------------------------------------------

_ICON_PATHS = {
    "anchor":
        "M12 2a3 3 0 0 0-1 5.83V10H8v2h3v8.94a8.5 8.5 0 0 1-6.41-5.94L7 13v-2H2v5"
        "a10.5 10.5 0 0 0 20 0v-5h-5v2l2.41 2a8.5 8.5 0 0 1-6.41 5.94V12h3v-2h-3"
        "V7.83A3 3 0 0 0 12 2zm0 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2z",
    "database":
        "M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.59 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4z"
        "m0 2c3.87 0 6 1.4 6 2s-2.13 2-6 2-6-1.4-6-2 2.13-2 6-2zm-6 4.18C7.5 9.69 9.6 10 12 10"
        "s4.5-.31 6-.82V12c0 .6-2.13 2-6 2s-6-1.4-6-2V9.18zm0 5C7.5 14.69 9.6 15 12 15"
        "s4.5-.31 6-.82V17c0 .6-2.13 2-6 2s-6-1.4-6-2v-2.82z",
    "tune":
        "M3 17v2h6v-2H3zm0-7v2h10v-2H3zm0-7v2h14V3H3zm12 4v2h6V7h-6zm-2 4v2h8v-2h-8z"
        "m4 4v2h4v-2h-4z",
    "rotate_right":
        "M15.55 5.55 11 1v3.07A8 8 0 0 0 4.07 11H1a8 8 0 0 0 13 6.32l-1.45-1.45"
        "A6 6 0 1 1 11 6.07V9l4.55-3.45z",
    "bolt":
        "M11 21h-1l1-7H7.5c-.88 0-.33-.75-.31-.78C8.48 10.94 10.42 7.54 13.01 3h1l-1 7"
        "h3.51c.4 0 .62.19.4.66C12.97 17.55 11 21 11 21z",
    "waves":
        "M17 16.99c-1.35 0-2.2.42-2.95.8-.65.33-1.18.6-2.05.6-.86 0-1.39-.27-2.04-.6"
        "-.75-.38-1.6-.8-2.95-.8s-2.2.42-2.95.8c-.65.33-1.17.6-2.04.6v2c1.35 0 2.2-.42"
        " 2.95-.8.65-.33 1.17-.6 2.04-.6.86 0 1.39.27 2.04.6.75.38 1.59.8 2.94.8"
        "s2.2-.42 2.95-.8c.65-.33 1.18-.6 2.05-.6.86 0 1.39.27 2.03.6.75.38 1.59.8 2.95.8"
        "v-2c-.86 0-1.39-.27-2.03-.6-.75-.38-1.59-.8-2.94-.8zm0-4.45c-1.35 0-2.2.43-2.95.8"
        "-.65.32-1.18.6-2.05.6-.86 0-1.39-.27-2.04-.6-.75-.38-1.6-.8-2.95-.8s-2.2.43-2.95.8"
        "-.65.32-1.17.6-2.04.6v2c1.35 0 2.2-.43 2.95-.8.65-.33 1.17-.6 2.04-.6.86 0 1.39.27"
        " 2.04.6.75.38 1.59.8 2.94.8s2.2-.43 2.95-.8c.65-.33 1.18-.6 2.05-.6.86 0 1.39.27 2.03.6"
        ".75.38 1.59.8 2.95.8v-2c-.86 0-1.39-.27-2.03-.6-.75-.38-1.59-.8-2.94-.8zm2.95-8.08"
        "c-.65.32-1.18.6-2.05.6-.86 0-1.39-.27-2.04-.6-.75-.39-1.6-.81-2.95-.81s-2.2.43-2.95.8"
        "-.65.32-1.17.6-2.04.6c-.87 0-1.39-.27-2.04-.6C5.13 3.43 4.27 3 2.92 3v2"
        "c.86 0 1.39.27 2.04.6.75.38 1.59.8 2.95.8s2.2-.43 2.95-.8c.65-.32 1.17-.6 2.04-.6"
        ".86 0 1.39.27 2.04.6.75.38 1.59.8 2.95.8s2.2-.43 2.95-.8c.65-.32 1.17-.6 2.04-.6V3"
        "c-1.34 0-2.2.43-2.95.8z",
    "dangerous":
        "M15.73 3H8.27L3 8.27v7.46L8.27 21h7.46L21 15.73V8.27L15.73 3z"
        "M17 15.74 15.74 17 12 13.26 8.26 17 7 15.74 10.74 12 7 8.26 8.26 7 12 10.74"
        " 15.74 7 17 8.26 13.26 12 17 15.74z",
    "check_circle":
        "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"
        "m-2 15-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
}


def hx_icon(name: str, size: str = "1.1em", color: str | None = None) -> str:
    """Return an inline SVG string for the given Material icon name."""
    path = _ICON_PATHS.get(name, "")
    fill = color if color else "currentColor"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}" fill="{fill}" '
        f'style="vertical-align:-0.22em;flex-shrink:0;display:inline-block;">'
        f'<path d="{path}"/></svg>'
    )


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --hx-accent:        #2f7fd1;
        --hx-accent-strong: #1f6aa5;
        --hx-pass-bg:       rgba(46,160,67,0.18);
        --hx-pass-fg:       #2ea043;
        --hx-fail-bg:       rgba(248,81,73,0.18);
        --hx-fail-fg:       #f85149;
        --hx-card-bg:       rgba(120,150,180,0.10);
        --hx-card-border:   rgba(120,150,180,0.22);
    }
    /* Inter for text only — never override icon fonts.
       Use :where() so specificity stays at 0, never beats Streamlit's
       own font-family declarations on Material Symbols spans. */
    :where(html, body, .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6,
           label, button, input, select, textarea) {
        font-family: 'Inter', system-ui, sans-serif;
    }

    /* Header brand */
    .hx-brand {
        display: flex; align-items: center; gap: 0.7rem;
        margin-bottom: 0.15rem;
    }
    .hx-brand svg { color: var(--hx-accent); }
    .hx-wordmark {
        font-size: 2.05rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(90deg, #3aa1ff 0%, #1f6aa5 60%, #0a3d6b 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; color: transparent;
    }
    .hx-tagline {
        color: var(--text-color, #5b6a7c); opacity: 0.78;
        font-size: 0.92rem; margin: 0 0 0.6rem 0; font-weight: 500;
    }

    /* Cards — translucent overlay → adapt to light + dark theme */
    .stat-card {
        background: var(--hx-card-bg);
        border: 1px solid var(--hx-card-border);
        border-left: 4px solid var(--hx-accent);
        padding: 0.65rem 0.95rem;
        border-radius: 6px;
        margin-bottom: 0.55rem;
    }
    .stat-card b      { color: inherit; }
    .stat-card small  { color: inherit; opacity: 0.78; }

    /* Verdict pills */
    .verdict-pass {
        background: var(--hx-pass-bg); color: var(--hx-pass-fg);
        padding: 4px 12px; border-radius: 999px;
        font-weight: 700; letter-spacing: 0.02em;
        border: 1px solid rgba(46,160,67,0.45);
    }
    .verdict-fail {
        background: var(--hx-fail-bg); color: var(--hx-fail-fg);
        padding: 4px 12px; border-radius: 999px;
        font-weight: 700; letter-spacing: 0.02em;
        border: 1px solid rgba(248,81,73,0.45);
    }

    /* Inline icon colour helpers */
    .hx-ico-accent svg { color: var(--hx-accent); }
    .hx-ico-pass   svg { color: var(--hx-pass-fg); }
    .hx-ico-fail   svg { color: var(--hx-fail-fg); }

    /* Sidebar polish */
    section[data-testid="stSidebar"] h2 {
        font-size: 0.78rem; text-transform: uppercase;
        letter-spacing: 0.12em; opacity: 0.75; margin-bottom: 0.4rem;
        display: flex; align-items: center; gap: 0.45rem;
    }
    section[data-testid="stSidebar"] h2 svg { color: var(--hx-accent); }
    section[data-testid="stSidebar"] hr { margin: 0.9rem 0; }

    /* Tabs polish */
    button[data-baseweb="tab"] { font-weight: 600; }

    /* Tighten metric labels */
    div[data-testid="stMetricValue"] { font-weight: 700; }

    /* Plotly bg transparency so dark theme shows through edges */
    .stPlotlyChart { border-radius: 8px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="hx-brand">
        {hx_icon("anchor", size="2.2rem")}
        <span class="hx-wordmark">Hydronix</span>
    </div>
    <p class="hx-tagline">
        First-principles ship hydrostatics &amp; stability suite
        &nbsp;·&nbsp; Wavez 2026 &nbsp;·&nbsp; IIT Madras
        <br/>
        <span style="opacity:0.65;">by Kavin Charles &amp; Jeevika R</span>
    </p>
    """,
    unsafe_allow_html=True,
)
st.write("")


# ---------------------------------------------------------------------------
# Sidebar – data source + run parameters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        f'<h2>{hx_icon("database")}&nbsp; Offset Data</h2>',
        unsafe_allow_html=True,
    )

    src = st.radio(
        "Source",
        ["Built-in benchmark", "Upload file (JSON/CSV/XLSX)", "Sample files"],
        index=0,
    )

    hull: Hull | None = None
    load_err = ""

    if src == "Built-in benchmark":
        which = st.selectbox(
            "Benchmark",
            [
                "Hackathon PS — ULCV (420×63×37.27, T=28.5)",
                "Box Barge (60×12×6)",
                "Wigley Hull (100×10×6.25)",
            ],
        )
        if which.startswith("Hackathon"):
            try:
                hull = hackathon_ps_hull()
                st.caption("Official Wavez 2026 Problem-Statement offset table "
                           "(ULCV, CB ≈ 0.78). Loaded from samples/.")
            except FileNotFoundError as e:
                st.error(str(e))
        elif which.startswith("Box"):
            L = st.number_input("L (m)", 10.0, 400.0, 60.0, 1.0)
            B = st.number_input("B (m)", 2.0, 60.0,  12.0, 0.5)
            D = st.number_input("D (m)", 1.0, 40.0,   6.0, 0.5)
            hull = box_barge(L=L, B=B, D=D, n_stations=21, n_waterlines=13)
        else:
            L = st.number_input("L (m)", 10.0, 400.0, 100.0,  1.0)
            B = st.number_input("B (m)", 2.0,  60.0,  10.0,  0.5)
            D = st.number_input("D (m)", 1.0,  40.0,   6.25, 0.5)
            hull = wigley_hull(L=L, B=B, D=D, n_stations=41, n_waterlines=21)

    elif src == "Upload file (JSON/CSV/XLSX)":
        up = st.file_uploader("Drop ship offset file",
                              type=["json", "csv", "tsv", "xlsx", "xls"])
        if up is not None:
            try:
                tmp = ROOT / "output" / f"_upload{Path(up.name).suffix}"
                tmp.parent.mkdir(exist_ok=True)
                tmp.write_bytes(up.getbuffer())
                hull = load_hull_file(tmp)
            except Exception as e:
                load_err = str(e)

    else:
        files = sorted((ROOT / "samples").glob("*.json")) + \
                sorted((ROOT / "samples").glob("*.csv"))
        if files:
            picked = st.selectbox("Sample", [f.name for f in files])
            try:
                hull = load_hull_file(ROOT / "samples" / picked)
            except Exception as e:
                load_err = str(e)
        else:
            st.info("No sample files found. Run `python samples/generate_samples.py`.")

    if load_err:
        st.error(f"Load failed: {load_err}")

    st.divider()
    st.markdown(
        f'<h2>{hx_icon("tune")}&nbsp; Run Parameters</h2>',
        unsafe_allow_html=True,
    )
    draft = st.number_input("Design draft T (m)", 0.10, 50.0, 3.0, 0.1)
    KG    = st.number_input("KG – vertical centre of gravity (m)", 0.0, 50.0, 3.0, 0.1)
    rho   = st.number_input("Water density ρ (t/m³)", 0.9, 1.1, 1.025, 0.001, format="%.3f")

    st.divider()
    st.markdown(
        f'<h2>{hx_icon("rotate_right")}&nbsp; Heel Sweep</h2>',
        unsafe_allow_html=True,
    )
    a_lo = st.number_input("φ min (°)",   0.0,  90.0,  0.0, 1.0)
    a_hi = st.number_input("φ max (°)",   1.0, 180.0, 80.0, 1.0)
    a_st = st.number_input("Δφ step (°)", 0.5,  30.0,  5.0, 0.5)

    st.divider()
    run = st.button("Run Analysis", type="primary", width="stretch",
                     icon=":material/play_circle:")
    if run:
        st.session_state["analyzed"] = True
    if st.button("Reset", width="stretch", icon=":material/refresh:"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

if hull is None:
    st.info("← Pick an offset source in the sidebar.")
    st.stop()

# Apply user-chosen rho (hull is frozen; rebuild with new rho)
if abs(hull.rho - rho) > 1e-6:
    hull = Hull(hull.stations, hull.waterlines, hull.half_breadths,
                name=hull.name, rho=rho)

# Basic info card
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ship",    hull.name)
c2.metric("LBP",     f"{hull.L:.2f} m")
c3.metric("B max",   f"{hull.B_max:.2f} m")
c4.metric("Depth D", f"{hull.D:.2f} m")

if not st.session_state.get("analyzed"):
    st.info("Press **Run Analysis** in the sidebar to compute.")
    with st.expander("Preview – Body Plan"):
        fig = plots.plot_body_plan(hull, draft=draft, ship_name=hull.name)
        st.pyplot(fig, clear_figure=True)
    st.stop()


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

with st.spinner("Computing upright hydrostatics …"):
    try:
        hs = Hydrostatics(hull, draft=draft, KG=KG)
    except ValueError as ex:
        st.error(f"Hydrostatics failed: {ex}")
        st.stop()
    s = hs.summary()

with st.spinner("Computing heeled GZ curve (polygon-clipping solver) …"):
    ang  = np.arange(a_lo, a_hi + 1e-9, a_st, dtype=float)
    ang_t, gz_t = gz_curve_true(hull, draft=draft, KG=KG, angles_deg=ang)
    _,     kn_t = kn_curve_true(hull, draft=draft, KG=KG, angles_deg=ang)
    ang_w, gz_w = gz_curve_wallsided(hs, angles_deg=ang)
    params = stability_parameters(ang_t, gz_t, hs.GM)
    imo    = imo_intact_stability_check(params)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

(tab_over, tab_hyd, tab_gz, tab_imo, tab_curves, tab_3d,
 tab_capsize, tab_extra, tab_export) = st.tabs(
    [
        ":material/dashboard: Overview",
        ":material/water: Hydrostatics",
        ":material/show_chart: GZ / KN",
        ":material/verified: IMO A.749",
        ":material/area_chart: Curves of Form",
        ":material/view_in_ar: 3-D Hull",
        ":material/bolt: Capsize Sim",
        ":material/balance: Trim / FS / Weather",
        ":material/download: Export",
    ]
)


# -------------------------------------- Overview
with tab_over:
    st.subheader("Summary at a glance")
    cA, cB, cC, cD = st.columns(4)
    cA.markdown(f"<div class='stat-card'><b>Displacement Δ</b><br>"
                f"{s['displacement_t']:.2f} t<br>"
                f"<small>{s['displacement_m3']:.2f} m³</small></div>",
                unsafe_allow_html=True)
    cB.markdown(f"<div class='stat-card'><b>Waterplane Aw</b><br>"
                f"{s['waterplane_area_m2']:.2f} m²<br>"
                f"<small>TPC = {s['TPC_t_per_cm']:.2f} t/cm</small></div>",
                unsafe_allow_html=True)
    cC.markdown(f"<div class='stat-card'><b>GM</b><br>"
                f"{s['GM_m']:.3f} m<br>"
                f"<small>KM={s['KM_m']:.3f}  KG={s['KG_m']:.3f}</small></div>",
                unsafe_allow_html=True)
    verdict_html = ("<span class='verdict-pass'>PASS</span>"
                    if imo["overall"] == "PASS"
                    else "<span class='verdict-fail'>FAIL</span>")
    cD.markdown(f"<div class='stat-card'><b>IMO 2008 IS Code</b><br>"
                f"{verdict_html}<br>"
                f"<small>{imo['passed']} / {imo['passed']+imo['failed']} criteria</small></div>",
                unsafe_allow_html=True)

    # Roll period card (extra row)
    roll_s = hs.roll_period()
    st.markdown(
        f"<div class='stat-card'>"
        f"<b>Natural Roll Period T\u03c6</b> &nbsp; {roll_s:.2f} s"
        f"<small style='margin-left:1em;color:#666;'>"
        f"k<sub>xx</sub> = 0.35·B = {0.35*hull.B_max:.2f} m &nbsp;|&nbsp; "
        f"GM = {s['GM_m']:.3f} m &nbsp;|&nbsp; "
        f"Tupper §5.3 empirical</small></div>",
        unsafe_allow_html=True,
    )

    st.divider()
    fig = plots.plot_dashboard(hull, hs, ang_t, gz_t, ang_w, gz_w,
                               params, imo, ship_name=hull.name)
    st.pyplot(fig, clear_figure=True)


# -------------------------------------- Hydrostatics
with tab_hyd:
    st.subheader("Upright Hydrostatic Properties")
    left, right = st.columns([1.2, 1])
    with left:
        rows = [
            ("Displacement volume ∇",    s["displacement_m3"],    "m³"),
            ("Displacement Δ",           s["displacement_t"],     "t"),
            ("Waterplane area Aw",       s["waterplane_area_m2"], "m²"),
            ("Midship section Am",       s["Am_m2"],              "m²"),
            ("TPC",                      s["TPC_t_per_cm"],       "t/cm"),
            ("MCTC",                     s["MCTC_tm_per_cm"],     "t·m/cm"),
            ("LCB from AP",              s["lcb_from_ap_m"],      "m"),
            ("LCF from AP",              s["lcf_from_ap_m"],      "m"),
            ("KB",                       s["KB_m"],               "m"),
            ("BM",                       s["BM_m"],               "m"),
            ("KM",                       s["KM_m"],               "m"),
            ("KG",                       s["KG_m"],               "m"),
            ("GM (KM−KG)",               s["GM_m"],               "m"),
            ("BML",                      s["BML_m"],              "m"),
            ("GML",                      s["GML_m"],              "m"),
            ("IT (waterplane)",          s["IT_m4"],              "m⁴"),
            ("IL (waterplane)",          s["IL_m4"],              "m⁴"),
            ("Cb",                       s["Cb"],                 "–"),
            ("Cw",                       s["Cw"],                 "–"),
            ("Cm",                       s["Cm"],                 "–"),
            ("Cp",                       s["Cp"],                 "–"),
            ("Cvp",                      s["Cvp"],                "–"),
            ("Roll period Tφ (C=0.35)",  s["roll_period_s"],      "s"),
        ]
        df = pd.DataFrame(rows, columns=["Parameter", "Value", "Unit"])
        df["Value"] = df["Value"].apply(lambda v: f"{v:,.4f}" if isinstance(v, (int, float)) else v)
        st.dataframe(df, hide_index=True, width="stretch", height=620)

    with right:
        fig = plots.plot_body_plan(hull, draft=draft, ship_name=hull.name)
        st.pyplot(fig, clear_figure=True)

    st.caption(
        f"Richardson-extrapolated integration error on ∇ "
        f"≈ {s['integration_error_estimate']:.3e} m³ "
        f"({s['integration_error_estimate']/max(s['displacement_m3'],1e-12)*100:.4f} %)"
    )


# -------------------------------------- GZ / KN
with tab_gz:
    st.subheader("Static Stability – GZ & KN Curves")
    fig = plots.plot_gz_curve(ang_t, gz_t, ang_w, gz_w, params,
                              ship_name=hull.name)
    st.pyplot(fig, clear_figure=True)

    cols = st.columns(4)
    cols[0].metric("GZ @ 30°",  f"{params['GZ_at_30deg_m']:.3f} m")
    cols[1].metric("GZ @ 40°",  f"{params['GZ_at_40deg_m']:.3f} m")
    cols[2].metric("GZ max",    f"{params['max_GZ_m']:.3f} m",
                   f"@ {params['angle_max_GZ_deg']:.1f}°")
    cols[3].metric("AVS",
                   f"{params['angle_vanishing_deg']:.1f}°" if not np.isnan(params['angle_vanishing_deg'])
                   else ">80°")

    df_gz = pd.DataFrame({
        "φ (°)":        ang_t,
        "GZ true (m)":  gz_t,
        "GZ wall (m)":  gz_w,
        "KN (m)":       kn_t,
    })
    st.dataframe(df_gz, hide_index=True, width="stretch")


# -------------------------------------- IMO
with tab_imo:
    st.subheader("IMO 2008 IS Code – Intact Stability (Part A)")
    overall_class = "verdict-pass" if imo["overall"] == "PASS" else "verdict-fail"
    st.markdown(
        f"<h3>Overall verdict: "
        f"<span class='{overall_class}'>{imo['overall']}</span> "
        f"<small>({imo['passed']} passed / {imo['failed']} failed)</small></h3>",
        unsafe_allow_html=True,
    )

    df_imo = pd.DataFrame([{
        "Criterion": c["description"],
        "Limit":     c["limit"],
        "Actual":    c["actual"],
        "Margin":    c["margin"],
        "Unit":      c["unit"],
        "Status":    c["status"],
    } for c in imo["criteria"]])
    st.dataframe(df_imo, hide_index=True, width="stretch")

    fig = plots.plot_imo_criteria(imo, ship_name=hull.name)
    st.pyplot(fig, clear_figure=True)


# -------------------------------------- Curves of form
with tab_curves:
    st.subheader("Curves of Form – hydrostatic particulars vs draft")
    n_drafts = st.slider("Number of drafts", 4, 20, 10)
    T_grid = np.linspace(0.1 * hull.D, min(draft * 1.3, 0.95 * hull.D), n_drafts)
    with st.spinner("Computing hydrostatic table …"):
        table = hydrostatic_table(hull, T_grid.tolist(), KG=KG)
    fig = plots.plot_hydrostatic_curves(table, ship_name=hull.name)
    st.pyplot(fig, clear_figure=True)

    df_tab = pd.DataFrame(table)
    st.dataframe(df_tab, hide_index=True, width="stretch", height=300)

    st.subheader("Bonjean Curves")
    with st.spinner("Computing Bonjean curves …"):
        bj = bonjean_curves(hull, dT=max(0.05, hull.D / 30.0))
    fig = plots.plot_bonjean(bj, ship_name=hull.name)
    st.pyplot(fig, clear_figure=True)

    st.subheader("Cross-curves of stability (KN vs Δ at fixed φ)")
    if st.checkbox("Compute cross-curves (slower)"):
        cc_drafts = st.multiselect("Drafts (m)",
                                   options=[round(t, 2) for t in T_grid],
                                   default=[round(t, 2) for t in T_grid[::max(1, n_drafts // 4)]])
        if cc_drafts:
            with st.spinner("Cross curves computing …"):
                cc = cross_curves_true(hull, cc_drafts, KG=KG,
                                       angles_deg=[10, 20, 30, 40, 50, 60])
            fig = plots.plot_kn_curves(np.array(cc["angles_deg"]),
                                       cc["kn_matrix"],
                                       cc["displacements_t"],
                                       ship_name=hull.name)
            st.pyplot(fig, clear_figure=True)


# -------------------------------------- 3D hull
with tab_3d:
    st.subheader("Interactive 3-D Hull Visualisations")

    viz_tabs = st.tabs([
        "Hull + B/G/M",
        "Heel Sweep",
        "Draft Rise",
        "GZ Surface",
        "Station Section",
    ])

    # ── Hull + B/G/M markers ───────────────────────────────────────────
    with viz_tabs[0]:
        st.caption("Static hull with centre of buoyancy **B**, centre of gravity **G**, "
                   "and metacentre **M** shown at any heel angle.")
        phi_bgm = st.slider("Heel angle φ (°)", 0.0, 60.0, 0.0, 1.0,
                             key="phi_bgm")
        try:
            fig_bgm = plots3d.hull_3d_with_points(hull, draft, KG, heel_deg=phi_bgm)
            st.plotly_chart(fig_bgm, width="stretch")
        except Exception as ex:
            st.error(f"B/G/M plot failed: {ex}")

    # ── Heel sweep animation ───────────────────────────────────────────
    with viz_tabs[1]:
        st.caption("Animated heel sweep. Watch **B** trace its arc as the ship heels. "
                   "Dashed green arm = GZ lever at each angle.")
        col_hs1, col_hs2 = st.columns(2)
        max_phi_sweep = col_hs1.slider("Max heel (°)", 10.0, 80.0, 60.0, 5.0,
                                        key="max_phi_sweep")
        step_sweep = col_hs2.slider("Step (°)", 1.0, 10.0, 5.0, 1.0,
                                    key="step_sweep")
        if st.button("Generate heel sweep", key="btn_heel_sweep",
                      icon=":material/play_arrow:"):
            with st.spinner("Computing heeled hydrostatics for each angle …"):
                try:
                    ang_sweep = np.arange(0, max_phi_sweep + 1e-9, step_sweep)
                    st.session_state["fig_heel_sweep"] = plots3d.hull_3d_heel_sweep_animation(
                        hull, draft, KG, angles_deg=ang_sweep)
                except Exception as ex:
                    st.error(f"Heel sweep failed: {ex}")
        if "fig_heel_sweep" in st.session_state:
            st.plotly_chart(st.session_state["fig_heel_sweep"], width="stretch")

    # ── Draft rise animation ───────────────────────────────────────────
    with viz_tabs[2]:
        st.caption("Waterplane rises from keel to design draft. "
                   "Blue = submerged, grey = emerged.")
        col_dr1, col_dr2 = st.columns(2)
        T_max_anim = col_dr1.slider("Max draft (m)", hull.D * 0.1, hull.D * 0.95,
                                     min(draft, hull.D * 0.9), 0.05,
                                     key="T_max_anim")
        n_dr_frames = col_dr2.slider("Frames", 10, 60, 40, 5, key="n_dr_frames")
        if st.button("Generate draft animation", key="btn_draft_anim",
                      icon=":material/play_arrow:"):
            with st.spinner("Building animation frames …"):
                try:
                    st.session_state["fig_draft_anim"] = plots3d.hull_3d_draft_animation(
                        hull, KG, T_max=T_max_anim, n_frames=n_dr_frames)
                except Exception as ex:
                    st.error(f"Draft animation failed: {ex}")
        if "fig_draft_anim" in st.session_state:
            st.plotly_chart(st.session_state["fig_draft_anim"], width="stretch")

    # ── GZ surface ────────────────────────────────────────────────────
    with viz_tabs[3]:
        st.caption("3-D surface of **GZ(φ, T)**. "
                   "Blue = stable, red = capsizing. "
                   "Orange line = design draft slice.")
        gc1, gc2, gc3, gc4 = st.columns(4)
        gz3_T_lo   = gc1.number_input("Draft min (m)", 0.1, hull.D * 0.8,
                                       hull.D * 0.3, 0.1, key="gz3_T_lo")
        gz3_hi_min = gz3_T_lo + 0.5
        gz3_hi_def = max(gz3_hi_min, min(hull.D * 0.9, draft * 1.2))
        gz3_T_hi   = gc2.number_input("Draft max (m)", gz3_hi_min, hull.D * 0.95,
                                       gz3_hi_def, 0.1, key="gz3_T_hi")
        gz3_n_draf = gc3.slider("# draft slices", 4, 14, 8, 1, key="gz3_nd")
        gz3_n_heel = gc4.slider("# heel angles", 5, 20, 10, 1, key="gz3_nh")
        if st.button("Compute GZ surface", key="btn_gz3d",
                      icon=":material/play_arrow:"):
            with st.spinner("Running polygon-clip solver over grid …"):
                try:
                    st.session_state["fig_gz_surface"] = plots3d.gz_surface_3d(
                        hull, KG,
                        draft_range=(gz3_T_lo, gz3_T_hi),
                        n_drafts=gz3_n_draf,
                        n_heels=gz3_n_heel,
                        design_draft=draft,
                    )
                except Exception as ex:
                    st.error(f"GZ surface failed: {ex}")
        if "fig_gz_surface" in st.session_state:
            st.plotly_chart(st.session_state["fig_gz_surface"], width="stretch")

    # ── Station cross-section ─────────────────────────────────────────
    with viz_tabs[4]:
        st.caption("Cross-section at any station. Coloured waterlines at multiple "
                   "heel angles. Shaded polygon = submerged area at max heel.")
        sc1, sc2 = st.columns([1, 2])
        sta_frac = sc1.slider("Station (% L from AP)", 0, 100, 50, 5,
                               key="sta_frac") / 100.0
        heel_list_raw = sc2.text_input(
            "Heel angles (°, comma-separated)", "0, 15, 30, 45",
            key="heel_list_cs")
        try:
            heel_list = [float(x.strip()) for x in heel_list_raw.split(",") if x.strip()]
        except ValueError:
            heel_list = [0, 15, 30, 45]
        try:
            fig_cs = plots3d.station_cross_section_figure(
                hull, draft, heel_angles=heel_list, station_frac=sta_frac)
            st.plotly_chart(fig_cs, width="stretch")
        except Exception as ex:
            st.error(f"Cross-section failed: {ex}")


# -------------------------------------- Capsize Simulator
with tab_capsize:
    st.markdown(
        '<h3 style="margin-bottom:0.2rem;display:flex;align-items:center;gap:0.45rem;">'
        + f'<span style="color:var(--hx-accent);">{hx_icon("bolt", size="1.4rem")}</span>'
        + ' Capsize Simulator '
        + '<small style="font-weight:500;opacity:0.7;">— nonlinear time-domain roll dynamics</small>'
        + '</h3>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Solves  **I · φ̈ + b · φ̇ + Δ·g · GZ(φ) = M_wave(t)**  using your "
        "polygon-clip GZ curve as the restoring-moment term. "
        "Watch the ship oscillate, decay, or capsize in real time."
    )

    cL, cR = st.columns([1, 1])
    with cL:
        phi0 = st.slider("Initial heel φ₀ (°)", -70.0, 70.0, 25.0, 1.0,
                          help="Release angle. Try >|AVS| to force a capsize.")
        phi_dot0 = st.slider("Initial angular rate φ̇₀ (°/s)",
                              -30.0, 30.0, 0.0, 0.5)
        duration = st.slider("Simulation duration (s)", 10.0, 300.0, 90.0, 5.0)
        C_roll   = st.slider("k_xx / B  (roll radius of gyration)",
                              0.25, 0.50, 0.35, 0.01,
                              help="Tupper §5.3: 0.33 fine, 0.35 displacement, 0.40 full.")
        zeta = st.slider("Damping ratio ζ", 0.00, 0.30, 0.05, 0.01,
                          help="0.03–0.05 typical; higher ζ = quicker decay.")

    with cR:
        mode = st.radio("Wave excitation",
                         ["calm (free decay)", "beam (sinusoidal)", "rogue (Gaussian pulse)"],
                         index=0)
        mode_key = mode.split()[0]
        wave_amp_MNm = st.number_input(
            "Wave moment amplitude (MN·m)",
            0.0, 2000.0, 0.0 if mode_key == "calm" else 80.0, 5.0,
            help="1 MN·m = 10⁶ N·m. Scale with Δ·g·GZ_max for realistic beam-sea moments."
        )
        wave_period = st.number_input(
            "Wave encounter period (s)", 3.0, 25.0,
            max(3.0, s.get("roll_period_s", 10.0)), 0.5,
            help="Resonance hits at Tₑ = Tφ = 2π/ωₙ."
        )
        avs_override = st.checkbox(
            "Override AVS from GZ curve", value=False,
            help="By default capsize threshold taken from solver AVS."
        )
        avs_val = st.number_input("AVS (°) if override", 10.0, 90.0, 60.0, 1.0) \
                   if avs_override else None

    run_sim = st.button("Run capsize simulation", type="primary",
                         icon=":material/rocket_launch:")

    if run_sim:
        from hydro.seakeeping import simulate_roll
        with st.spinner("Integrating nonlinear roll ODE …"):
            st.session_state["capsize_result"] = simulate_roll(
                gz_angles_deg  = ang_t,
                gz_values_m    = gz_t,
                displacement_t = s["displacement_t"],
                B_m            = hull.B_max,
                GM_m           = s["GM_m"],
                phi0_deg       = phi0,
                phi_dot0_degps = phi_dot0,
                duration_s     = duration,
                mode           = mode_key,
                wave_amp_Nm    = wave_amp_MNm * 1.0e6,
                wave_period_s  = wave_period,
                C_roll         = C_roll,
                zeta           = zeta,
                avs_deg        = avs_val,
                n_points       = max(400, int(duration * 8)),
            )

    if "capsize_result" in st.session_state:
        from hydro import plots3d
        import plotly.graph_objects as go
        result = st.session_state["capsize_result"]

        # Verdict strip
        vL, v1, v2, v3, v4 = st.columns([1.2, 1, 1, 1, 1])
        if result.capsized:
            vL.markdown(
                f"<div class='stat-card' style='background:var(--hx-fail-bg);"
                f"border-left-color:var(--hx-fail-fg);'>"
                f"<b style='font-size:1.4rem;color:var(--hx-fail-fg);"
                f"display:inline-flex;align-items:center;gap:0.4rem;'>"
                f"{hx_icon('dangerous', size='1.5rem', color='var(--hx-fail-fg)')}"
                f" CAPSIZED</b><br>"
                f"<small>at t = {result.capsize_time_s:.1f} s</small></div>",
                unsafe_allow_html=True)
        else:
            vL.markdown(
                f"<div class='stat-card' style='background:var(--hx-pass-bg);"
                f"border-left-color:var(--hx-pass-fg);'>"
                f"<b style='font-size:1.4rem;color:var(--hx-pass-fg);"
                f"display:inline-flex;align-items:center;gap:0.4rem;'>"
                f"{hx_icon('check_circle', size='1.5rem', color='var(--hx-pass-fg)')}"
                f" SURVIVED</b><br>"
                f"<small>oscillating / decaying</small></div>",
                unsafe_allow_html=True)
        v1.metric("Max heel",      f"{result.max_heel_deg:.1f}°")
        v2.metric("Natural Tφ",    f"{result.period_s:.2f} s")
        v3.metric("Damping ζ",     f"{result.zeta:.3f}")
        v4.metric("AVS used",      f"{result.avs_used_deg:.1f}°")

        # φ(t) time history
        phi_deg_t = np.degrees(result.phi)
        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(
            x=result.t, y=phi_deg_t, mode='lines',
            line=dict(color='#1f6aa5', width=2),
            name="φ(t)",
        ))
        avs_line = result.avs_used_deg
        fig_t.add_hrect(y0=avs_line,  y1=90,
                        fillcolor='rgba(211,51,51,0.15)', line_width=0,
                        annotation_text="capsize zone (+)",
                        annotation_position="top right")
        fig_t.add_hrect(y0=-90, y1=-avs_line,
                        fillcolor='rgba(211,51,51,0.15)', line_width=0,
                        annotation_text="capsize zone (−)",
                        annotation_position="bottom right")
        fig_t.add_hline(y=0, line=dict(color='grey', dash='dot', width=1))
        if result.capsized and np.isfinite(result.capsize_time_s):
            fig_t.add_vline(x=result.capsize_time_s,
                             line=dict(color='red', dash='dash', width=2),
                             annotation_text=f"capsize @ {result.capsize_time_s:.1f}s")
        fig_t.update_layout(
            title="Roll angle φ(t) – time history",
            xaxis_title="t (s)", yaxis_title="φ (°)",
            height=360, template="plotly_white",
            yaxis=dict(range=[-max(90, result.max_heel_deg * 1.2),
                                max(90, result.max_heel_deg * 1.2)]),
        )
        st.plotly_chart(fig_t, width="stretch")

        # Two side-by-side: phase portrait + wave moment
        pcL, pcR = st.columns(2)
        with pcL:
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(
                x=phi_deg_t, y=np.degrees(result.phi_dot),
                mode='lines', line=dict(color='#d33', width=1.5),
                name='trajectory',
            ))
            fig_p.add_trace(go.Scatter(
                x=[phi_deg_t[0]], y=[np.degrees(result.phi_dot[0])],
                mode='markers', marker=dict(size=12, color='green', symbol='circle'),
                name='start',
            ))
            fig_p.add_trace(go.Scatter(
                x=[phi_deg_t[-1]], y=[np.degrees(result.phi_dot[-1])],
                mode='markers', marker=dict(size=12, color='black', symbol='x'),
                name='end',
            ))
            fig_p.update_layout(
                title="Phase portrait  φ̇  vs  φ",
                xaxis_title="φ (°)", yaxis_title="φ̇ (°/s)",
                height=340, template="plotly_white",
            )
            st.plotly_chart(fig_p, width="stretch")
        with pcR:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(
                x=result.t, y=result.M_wave / 1e6, mode='lines',
                line=dict(color='#7b3ca3', width=1.5),
                name="M_wave(t)",
            ))
            fig_m.update_layout(
                title="External wave moment (MN·m)",
                xaxis_title="t (s)", yaxis_title="M (MN·m)",
                height=340, template="plotly_white",
            )
            st.plotly_chart(fig_m, width="stretch")

        # 3-D rolling animation
        st.markdown(
            '<h3 style="display:flex;align-items:center;gap:0.45rem;">'
            + f'<span style="color:var(--hx-accent);">{hx_icon("waves", size="1.3rem")}</span>'
            + ' Live 3-D hull rolling in the earth frame</h3>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Press Play — the ship rotates about its longitudinal axis "
            "exactly as solved by the ODE above. Waterplane stays flat."
        )
        try:
            fig3d_anim = plots3d.hull_3d_rolling_animation(
                hull, draft=draft,
                phi_deg_t=np.degrees(result.phi),
                t_s=result.t,
                n_frames=60,
                title=hull.name,
            )
            st.plotly_chart(fig3d_anim, width="stretch")
        except Exception as ex:
            st.error(f"3-D animation failed: {ex}")

        with st.expander("Diagnostic – physics parameters used"):
            st.write({
                "mass_kg":       f"{result.mass_kg:,.0f}",
                "I_xx (kg·m²)":  f"{result.I_xx:,.0f}",
                "ω_n (rad/s)":   f"{result.omega_n:.4f}",
                "T_φ  (s)":      f"{result.period_s:.2f}",
                "ζ":             f"{result.zeta:.3f}",
                "AVS (°)":       f"{result.avs_used_deg:.2f}",
                "mode":          result.mode,
                "capsized":      result.capsized,
                "capsize_time":  result.capsize_time_s,
                "max_|φ|":       f"{result.max_heel_deg:.2f}°",
            })


# -------------------------------------- Trim / FS / Weather
with tab_extra:
    st.subheader("Equilibrium Trim Solver")
    with st.form("trim_form"):
        cc1, cc2 = st.columns(2)
        W    = cc1.number_input("Weight W (t)", 1.0,
                                 1e6, float(s["displacement_t"]), 1.0)
        LCG  = cc2.number_input("LCG from AP (m)", 0.0,
                                 float(hull.L), float(s["lcb_from_ap_m"]), 0.1)
        go_trim = st.form_submit_button("Solve equilibrium")
    if go_trim:
        with st.spinner("Newton-Raphson iterating …"):
            try:
                t_res = solve_equilibrium(hull, W=W, LCG=LCG, KG=KG)
                st.json({k: v for k, v in t_res.items() if k != "hydrostatics"})
            except Exception as ex:
                st.error(str(ex))

    st.divider()
    st.subheader("Free-Surface Correction (rectangular tank)")
    with st.form("fs_form"):
        f1, f2, f3 = st.columns(3)
        L_t   = f1.number_input("Tank length L_t (m)", 0.1, 100.0, 8.0, 0.1)
        B_t   = f2.number_input("Tank breadth B_t (m)", 0.1, 60.0, 6.0, 0.1)
        rho_f = f3.number_input("Liquid ρ (t/m³)", 0.1, 2.0, 0.85, 0.01)
        go_fs = st.form_submit_button("Compute FSM / GM corrected")
    if go_fs:
        fsm = fsm_rectangular_tank(L_t, B_t, rho_f)
        gmc = gm_corrected(hs.GM, fsm, s["displacement_t"])
        st.write(f"**Free-surface moment FSM** = {fsm:,.3f} t·m")
        st.write(f"**GM corrected (fluid)** = {gmc:.4f} m   (was GM = {hs.GM:.4f} m)")

    st.divider()
    st.subheader("Weather (Severe-Wind) Criterion — IMO A.749")
    with st.form("w_form"):
        w1, w2, w3, w4 = st.columns(4)
        A_proj = w1.number_input("Windage area (m²)",    1.0, 1e5, 400.0, 10.0)
        z_proj = w2.number_input("Windage lever Z (m)",  0.1,  40.0,   6.0, 0.1)
        OG_m   = w3.number_input("OG (G above WL, m)",  -20.0, 20.0,   0.0, 0.1)
        vw     = w4.number_input("Wind speed (m/s)",     5.0,  50.0,  26.0, 1.0)
        go_w   = st.form_submit_button("Check weather criterion")
    if go_w:
        try:
            wx = weather_criterion(
                displacement_t=s["displacement_t"],
                Aw_profile_m2=A_proj,
                Z_m=z_proj,
                gz_angles_deg=ang_t,
                gz_values_m=gz_t,
                OG_m=OG_m,
                draft_m=draft,
                wind_speed_mps=vw,
            )
            st.json(wx)
        except Exception as ex:
            st.error(str(ex))


# -------------------------------------- Export
with tab_export:
    st.subheader("Export Results")

    # JSON hull round-trip
    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, float) and (obj != obj):  # NaN
            return None
        return obj

    buf = io.StringIO()
    buf.write(json.dumps(_clean({
        **hull.to_dict(),
        "draft" : draft,
        "KG"    : KG,
        "hydrostatics": s,
        "stability"   : params,
        "imo"         : imo,
    }), indent=2, default=float))
    st.download_button(
        "Download full results (JSON)",
        buf.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_results.json",
        mime="application/json",
        icon=":material/download:",
    )

    # GZ curve CSV
    csv_buf = io.StringIO()
    pd.DataFrame({
        "phi_deg"     : ang_t,
        "GZ_true_m"   : gz_t,
        "GZ_wall_m"   : gz_w,
        "KN_m"        : kn_t,
    }).to_csv(csv_buf, index=False)
    st.download_button(
        "Download GZ / KN curve (CSV)",
        csv_buf.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_gz_curve.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    # Offset table CSV
    st.markdown("---")
    st.markdown("**Hull offset table**")
    rows_off = []
    for i, x in enumerate(hull.stations):
        for j, z in enumerate(hull.waterlines):
            rows_off.append({"station_m": x, "waterline_m": z,
                             "half_breadth_m": hull.half_breadths[i, j]})
    csv_off = io.StringIO()
    pd.DataFrame(rows_off).to_csv(csv_off, index=False)
    st.download_button(
        "Download offset table (CSV – long form)",
        csv_off.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_offsets.csv",
        mime="text/csv",
        icon=":material/download:",
    )
    # Hydrostatics table CSV
    T_grid_exp2 = np.linspace(max(0.1 * hull.D, 0.5), min(draft * 1.3, 0.95 * hull.D), 12)
    table_csv   = hydrostatic_table(hull, T_grid_exp2.tolist(), KG=KG)
    csv_hyd = io.StringIO()
    pd.DataFrame(table_csv).to_csv(csv_hyd, index=False)
    st.download_button(
        "Download hydrostatic table (CSV)",
        csv_hyd.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_hydrostatics.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    st.markdown("---")
    # PDF report
    if st.button("Generate PDF report", icon=":material/picture_as_pdf:"):
        from hydro.report import generate_pdf
        out_dir = ROOT / "output"
        out_dir.mkdir(exist_ok=True)
        stem = hull.name.replace(" ", "_").replace("/", "_")
        fig_paths = {
            "body_plan": str(out_dir / f"{stem}_body.png"),
            "gz"       : str(out_dir / f"{stem}_gz.png"),
            "curves"   : str(out_dir / f"{stem}_curves.png"),
            "bonjean"  : str(out_dir / f"{stem}_bonjean.png"),
            "imo"      : str(out_dir / f"{stem}_imo.png"),
        }
        out_pdf = out_dir / f"{stem}_report.pdf"
        with st.spinner("Rendering figures + PDF …"):
            try:
                plots.plot_body_plan(hull, draft=draft, ship_name=hull.name,
                                     save_path=fig_paths["body_plan"])
                plots.plot_gz_curve(ang_t, gz_t, ang_w, gz_w, params,
                                    ship_name=hull.name, save_path=fig_paths["gz"])
                T_grid_exp = np.linspace(0.1 * hull.D,
                                         min(draft * 1.3, 0.95 * hull.D), 10)
                table_exp  = hydrostatic_table(hull, T_grid_exp.tolist(), KG=KG)
                plots.plot_hydrostatic_curves(table_exp, ship_name=hull.name,
                                              save_path=fig_paths["curves"])
                bj_exp = bonjean_curves(hull, dT=max(0.05, hull.D / 30.0))
                plots.plot_bonjean(bj_exp, ship_name=hull.name,
                                   save_path=fig_paths["bonjean"])
                plots.plot_imo_criteria(imo, ship_name=hull.name,
                                        save_path=fig_paths["imo"])
                generate_pdf(
                    output_path   = out_pdf,
                    ship_name     = hull.name,
                    hydro_summary = s,
                    stab_params   = params,
                    imo_check     = imo,
                    figure_paths  = fig_paths,
                )
                st.success(f"Report written: {out_pdf}")
                st.download_button(
                    "Download PDF",
                    out_pdf.read_bytes(),
                    file_name=out_pdf.name,
                    mime="application/pdf",
                    icon=":material/download:",
                )
            except Exception as ex:
                st.error(f"PDF generation failed: {ex}")

st.caption(
    "Hydronix · Wavez 2026 · IIT Madras · "
    "Built by Kavin Charles & Jeevika R. "
    "Solver: composite Simpson 1/3 + 3/8, Richardson extrapolation, Shapely polygon clipping for true heeled hydrostatics."
)
