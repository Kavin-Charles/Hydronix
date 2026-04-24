"""
HydroHackathon — Streamlit Web UI
=================================

Interactive front-end for the first-principles hydrostatics solver.
Run with:

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
from hydro.benchmarks    import box_barge, wigley_hull
from hydro                import plots, plots3d


# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="HydroHackathon – Ship Hydrostatics",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title { font-size: 2.1rem; font-weight: 700; color: #1f3a5f; margin-bottom: 0; }
    .sub-title  { color: #5b6a7c; margin-top: 0; font-size: 0.95rem; }
    .stat-card  { background: #f4f7fa; border-left: 4px solid #1f6aa5; padding: 0.6rem 0.9rem;
                  border-radius: 4px; margin-bottom: 0.5rem; }
    .verdict-pass { background: #e4f7e6; color: #146c2e; padding: 4px 10px;
                    border-radius: 4px; font-weight: 600; }
    .verdict-fail { background: #fde4e2; color: #8a1912; padding: 4px 10px;
                    border-radius: 4px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">⚓ HydroHackathon – First-Principles Ship Hydrostatics</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    'Wavez 2026 · IIT Madras · Silver Voyage Hydrohackathon · Phase 1 solver'
    '</div>',
    unsafe_allow_html=True,
)
st.write("")


# ---------------------------------------------------------------------------
# Sidebar – data source + run parameters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("① Offset Data")

    src = st.radio(
        "Source",
        ["Built-in benchmark", "Upload file (JSON/CSV/XLSX)", "Sample files"],
        index=0,
    )

    hull: Hull | None = None
    load_err = ""

    if src == "Built-in benchmark":
        which = st.selectbox("Benchmark", ["Box Barge (60×12×6)", "Wigley Hull (100×10×6.25)"])
        if which.startswith("Box"):
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
    st.header("② Run Parameters")
    draft = st.number_input("Design draft T (m)", 0.10, 50.0, 3.0, 0.1)
    KG    = st.number_input("KG – vertical centre of gravity (m)", 0.0, 50.0, 3.0, 0.1)
    rho   = st.number_input("Water density ρ (t/m³)", 0.9, 1.1, 1.025, 0.001, format="%.3f")

    st.divider()
    st.header("③ Heel Sweep")
    a_lo = st.number_input("φ min (°)",   0.0,  90.0,  0.0, 1.0)
    a_hi = st.number_input("φ max (°)",   1.0, 180.0, 80.0, 1.0)
    a_st = st.number_input("Δφ step (°)", 0.5,  30.0,  5.0, 0.5)

    st.divider()
    run = st.button("🚀 Run Analysis", type="primary", use_container_width=True)


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

if not run:
    st.info("Press **Run Analysis** in the sidebar to compute.")
    # Still show body plan for preview
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

tab_over, tab_hyd, tab_gz, tab_imo, tab_curves, tab_3d, tab_extra, tab_export = st.tabs(
    ["Overview", "Hydrostatics", "GZ / KN", "IMO A.749", "Curves of Form",
     "3-D Hull", "Trim / FS / Weather", "Export"]
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
        st.dataframe(df, hide_index=True, use_container_width=True, height=620)

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
    st.dataframe(df_gz, hide_index=True, use_container_width=True)


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
    st.dataframe(df_imo, hide_index=True, use_container_width=True)

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
    st.dataframe(df_tab, hide_index=True, use_container_width=True, height=300)

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
    st.subheader("Interactive 3-D Hull View")
    show_tilt = st.checkbox("Show tilted waterplane", value=True)
    phi_3d = st.slider("Heel angle (°) for waterplane", 0.0, 60.0, 10.0, 1.0) if show_tilt else 0.0
    try:
        fig3d = plots3d.hull_3d_figure(hull, draft=draft,
                                       heel_deg=phi_3d if show_tilt else 0.0,
                                       title=hull.name)
        st.plotly_chart(fig3d, use_container_width=True)
    except Exception as ex:
        st.error(f"3-D plot failed: {ex}")


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
                st.json(t_res)
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
    buf = io.StringIO()
    buf.write(json.dumps({
        **hull.to_dict(),
        "draft" : draft,
        "KG"    : KG,
        "hydrostatics": s,
        "stability"   : params,
        "imo"         : imo,
    }, indent=2, default=float))
    st.download_button(
        "⬇ Download full results (JSON)",
        buf.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_results.json",
        mime="application/json",
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
        "⬇ Download GZ / KN curve (CSV)",
        csv_buf.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_gz_curve.csv",
        mime="text/csv",
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
        "⬇ Download offset table (CSV – long form)",
        csv_off.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_offsets.csv",
        mime="text/csv",
    )
    # Hydrostatics table CSV
    T_grid_exp2 = np.linspace(max(0.1 * hull.D, 0.5), min(draft * 1.3, 0.95 * hull.D), 12)
    table_csv   = hydrostatic_table(hull, T_grid_exp2.tolist(), KG=KG)
    csv_hyd = io.StringIO()
    pd.DataFrame(table_csv).to_csv(csv_hyd, index=False)
    st.download_button(
        "⬇ Download hydrostatic table (CSV)",
        csv_hyd.getvalue(),
        file_name=f"{hull.name.replace(' ', '_')}_hydrostatics.csv",
        mime="text/csv",
    )

    st.markdown("---")
    # PDF report
    if st.button("📄 Generate PDF report"):
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
                    "⬇ Download PDF",
                    out_pdf.read_bytes(),
                    file_name=out_pdf.name,
                    mime="application/pdf",
                )
            except Exception as ex:
                st.error(f"PDF generation failed: {ex}")

st.caption(
    "Built for HydroHackathon 2026 – Wavez · IIT Madras Ocean Engineering. "
    "Solver: composite Simpson 1/3 + 3/8, Richardson extrapolation, Shapely polygon clipping for true heeled hydrostatics."
)
