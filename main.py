"""
Hydronix – Command-Line Interface
==================================
Authors : Kavin Charles · Jeevika R
Event   : Wavez 2026 · IIT Madras

Usage examples
--------------
    python main.py                                         # run with default sample
    python main.py samples/wigley_hull.json
    python main.py samples/box_barge.json --table
    python main.py samples/mv_sample_vessel.json --imo --report
    python main.py samples/mv_sample_vessel.json --trim 6000 60     # W(t), LCG(m)
    python main.py samples/mv_sample_vessel.json --fsm "40,12,0.85" # rect tank
    python main.py samples/wigley_hull.json --validate              # benchmark run

Output
------
  * stdout: formatted hydrostatic + stability + IMO tables
  * output/<ship>_*.png  : all figures (when --save given)
  * output/<ship>.pdf    : full report (when --report given)
"""

from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path

import numpy as np

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------

from hydro.io_formats    import load
from hydro.hydrostatics  import Hydrostatics, hydrostatic_table
from hydro.heeled        import gz_curve_true, kn_curve_true, cross_curves_true
from hydro.stability     import gz_curve_wallsided, stability_parameters
from hydro.imo           import imo_intact_stability_check, format_report as imo_format
from hydro.trim          import solve_equilibrium
from hydro.bonjean       import bonjean_curves
from hydro.free_surface  import fsm_rectangular_tank, gm_corrected
from hydro.weather       import weather_criterion
from hydro import plots


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

SEP  = "═" * 64
SEP2 = "─" * 64

def _hdr(t):
    print(f"\n{SEP}\n  {t}\n{SEP}")

def _row(label, value, unit=""):
    print(f"  {label:<36s}{value!s:>14}  {unit}")


def print_hydrostatic_summary(s, ship_name):
    _hdr(f"HYDROSTATIC SUMMARY – {ship_name}")
    print(f"  L = {s['L_m']:.2f} m   B = {s['B_max_m']:.2f} m   "
          f"D = {s['D_m']:.2f} m   T = {s['draft_m']:.3f} m   "
          f"ρ = {s['rho_t_per_m3']:.3f} t/m³   KG = {s['KG_m']:.3f} m\n")

    print("  Volume and Weight")
    print(f"  {SEP2[:26]}")
    _row("Displacement volume ∇",           f"{s['displacement_m3']:.3f}",   "m³")
    _row("Displacement Δ",                  f"{s['displacement_t']:.3f}",    "t")

    print("\n  Waterplane")
    print(f"  {SEP2[:26]}")
    _row("Waterplane area Aw",              f"{s['waterplane_area_m2']:.3f}","m²")
    _row("Midship section area Am",         f"{s['Am_m2']:.3f}",             "m²")
    _row("TPC  (tonnes per cm)",            f"{s['TPC_t_per_cm']:.3f}",      "t/cm")

    print("\n  Longitudinal Centres")
    print(f"  {SEP2[:26]}")
    _row("LCB from AP",                     f"{s['lcb_from_ap_m']:.4f}",     "m")
    _row("LCF from AP",                     f"{s['lcf_from_ap_m']:.4f}",     "m")

    print("\n  Vertical Centres and Metacentres")
    print(f"  {SEP2[:30]}")
    _row("KB",                              f"{s['KB_m']:.4f}",              "m")
    _row("BM  (IT/∇)",                      f"{s['BM_m']:.4f}",              "m")
    _row("KM  (KB+BM)",                     f"{s['KM_m']:.4f}",              "m")
    _row("KG",                              f"{s['KG_m']:.4f}",              "m")
    _row("GM  (KM−KG)",                     f"{s['GM_m']:.4f}",              "m")
    _row("BML (IL/∇)",                      f"{s['BML_m']:.4f}",             "m")
    _row("GML",                             f"{s['GML_m']:.4f}",             "m")
    _row("MCTC",                            f"{s['MCTC_tm_per_cm']:.3f}",    "t·m/cm")

    print("\n  Form Coefficients")
    print(f"  {SEP2[:22]}")
    _row("Block coefficient Cb",            f"{s['Cb']:.5f}",                "")
    _row("Waterplane coefficient Cw",       f"{s['Cw']:.5f}",                "")
    _row("Midship coefficient Cm",          f"{s['Cm']:.5f}",                "")
    _row("Prismatic coefficient Cp",        f"{s['Cp']:.5f}",                "")
    _row("Vertical prismatic Cvp",          f"{s['Cvp']:.5f}",               "")

    err = s.get("integration_error_estimate", 0.0)
    if err and not np.isnan(err):
        print(f"\n  Richardson-extrapolation error on ∇ ≈ {err:.3e} m³ "
              f"({100 * err / max(s['displacement_m3'], 1e-9):.4f} %)")


def print_stability(ang_true, gz_true, ang_ws, gz_ws, kn, params):
    _hdr("STABILITY – GZ CURVE (true polygon + wall-sided reference)")
    print(f"  {'φ (°)':>6}  {'GZ true (m)':>13}  {'GZ wall-sided':>15}  "
          f"{'KN true (m)':>13}")
    print(f"  {SEP2[:55]}")
    for i, a in enumerate(ang_true):
        gz_t  = f"{gz_true[i]:+.4f}" if not np.isnan(gz_true[i]) else "   n/a "
        gz_w  = ("   n/a " if gz_ws is None or i >= len(gz_ws) or np.isnan(gz_ws[i])
                 else f"{gz_ws[i]:+.4f}")
        kn_s  = f"{kn[i]:+.4f}" if not np.isnan(kn[i]) else "   n/a "
        print(f"  {a:>6.1f}  {gz_t:>13}  {gz_w:>15}  {kn_s:>13}")

    print("\n  Stability Parameters")
    print(f"  {SEP2[:22]}")
    _row("Initial GM",                      f"{params['GM_m']:.4f}",             "m")
    _row("GZ at 30°",                       f"{params['GZ_at_30deg_m']:.4f}",    "m")
    _row("GZ at 40°",                       f"{params['GZ_at_40deg_m']:.4f}",    "m")
    _row("Maximum GZ",                      f"{params['max_GZ_m']:.4f}",         "m")
    _row("Heel at max GZ",                  f"{params['angle_max_GZ_deg']:.2f}", "°")
    _row("Area  0 → 30°",                   f"{params['area_0_30_m_rad']:.5f}",  "m·rad")
    _row("Area  0 → 40°",                   f"{params['area_0_40_m_rad']:.5f}",  "m·rad")
    _row("Area 30° → 40°",                  f"{params['area_30_40_m_rad']:.5f}", "m·rad")
    avs = params["angle_vanishing_deg"]
    _row("Angle of vanishing stability",
         f"{avs:.2f}" if not np.isnan(avs) else ">80", "°")


def print_hydrostatic_table(tab):
    _hdr("HYDROSTATIC TABLE – ACROSS DRAFTS")
    hdrs = ["T (m)", "Δ (t)", "Aw (m²)", "LCB (m)", "LCF (m)",
            "KB (m)", "BM (m)", "KM (m)", "GM (m)", "TPC", "MCTC", "Cb"]
    widths = [7, 10, 10, 9, 9, 8, 8, 8, 8, 7, 9, 7]
    print("  " + "  ".join(f"{h:>{w}}" for h, w in zip(hdrs, widths)))
    print("  " + "  ".join("─" * w for w in widths))
    keys = ["draft_m", "displacement_t", "waterplane_area_m2",
            "lcb_from_ap_m", "lcf_from_ap_m", "KB_m", "BM_m", "KM_m",
            "GM_m", "TPC_t_per_cm", "MCTC_tm_per_cm", "Cb"]
    fmt  = [".3f", ".2f", ".2f", ".3f", ".3f", ".3f", ".3f", ".3f",
            ".3f", ".3f", ".3f", ".4f"]
    for row in tab:
        cells = [f"{row[k]:>{w}{f}}" for k, w, f in zip(keys, widths, fmt)]
        print("  " + "  ".join(cells))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Hydronix – first-principles ship hydrostatics & stability"
                    " (Kavin Charles · Jeevika R, Wavez 2026)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default="samples/mv_sample_vessel.json",
                    help="JSON/CSV/XLSX offset file (default: samples/mv_sample_vessel.json)")
    ap.add_argument("--draft",      type=float, default=None, help="override design draft (m)")
    ap.add_argument("--KG",         type=float, default=None, help="override KG (m)")
    ap.add_argument("--rho",        type=float, default=None, help="override density (t/m³)")
    ap.add_argument("--angles",     type=str,   default="0:80:5",
                    help="heel angle range 'lo:hi:step' (default 0:80:5)")
    ap.add_argument("--no-heeled",  action="store_true", help="skip true-heeled GZ (fast)")
    ap.add_argument("--table",      action="store_true", help="print hydrostatic table")
    ap.add_argument("--imo",        action="store_true", help="print IMO criteria check")
    ap.add_argument("--trim",       type=str, default=None,
                    metavar="W_t,LCG_m", help="equilibrium trim solve")
    ap.add_argument("--fsm",        type=str, default=None,
                    metavar="L,B,rho",
                    help="add rectangular free-surface tank (length,breadth,rho_liq)")
    ap.add_argument("--weather",    action="store_true",
                    help="evaluate IMO severe-wind-and-rolling criterion")
    ap.add_argument("--save",       action="store_true", help="save plots as PNG")
    ap.add_argument("--report",     action="store_true", help="generate PDF report")
    ap.add_argument("--no-plot",    action="store_true", help="skip plots entirely")
    ap.add_argument("--validate",   action="store_true", help="run benchmark validation")
    args = ap.parse_args()

    if args.validate:
        from tests import test_benchmarks   # noqa: F401
        sys.exit(test_benchmarks.__name__ and 0)

    # ── Load hull ─────────────────────────────────────────────────────────
    in_path = Path(args.input)
    print(f"\n  Loading: {in_path}")
    hull = load(in_path, rho=args.rho if args.rho else 1.025)
    if args.rho:
        hull = hull.__class__(hull.stations, hull.waterlines, hull.half_breadths,
                              name=hull.name, rho=args.rho)

    # Pull draft/KG from the file if not overridden
    try:
        meta = json.loads(in_path.read_text(encoding="utf-8")) \
               if in_path.suffix.lower() == ".json" else {}
    except Exception:
        meta = {}
    draft = args.draft if args.draft is not None else float(meta.get("draft", 0.5 * hull.D))
    KG    = args.KG    if args.KG    is not None else float(meta.get("KG",    0.6 * draft))

    hs = Hydrostatics(hull, draft, KG)
    summary = hs.summary()
    print_hydrostatic_summary(summary, hull.name)

    # ── Free-surface correction ───────────────────────────────────────────
    fsm_total = 0.0
    if args.fsm:
        L_t, B_t, rho_l = (float(x) for x in args.fsm.split(","))
        fsm_total = fsm_rectangular_tank(L_t, B_t, rho_l)
        gm_eff    = gm_corrected(hs.GM, fsm_total, hs.displacement)
        _hdr("FREE-SURFACE CORRECTION")
        _row(f"Tank {L_t:.1f}×{B_t:.1f} m, ρ_liq={rho_l:.3f}",
             f"FSM = {fsm_total:.2f}", "t·m")
        _row("Virtual rise of G  (FSM/Δ)",  f"{fsm_total/hs.displacement:.4f}", "m")
        _row("Effective GM (fluid)",        f"{gm_eff:.4f}",                    "m")

    # ── Heel angles ───────────────────────────────────────────────────────
    lo, hi, step = (float(x) for x in args.angles.split(":"))
    angles = np.arange(lo, hi + 0.5 * step, step, dtype=float)

    # Wall-sided reference (always cheap)
    ang_ws, gz_ws = gz_curve_wallsided(hs, angles, limit_deg=25.0)

    # True heeled (slower – polygon clipping)
    if args.no_heeled:
        ang_true, gz_true = angles, gz_ws.copy()   # fallback
        print("\n  [ --no-heeled ]  using wall-sided as the primary curve")
    else:
        print(f"\n  Computing true-heeled GZ at {len(angles)} angles "
              f"(polygon-clipping solver) …")
        ang_true, gz_true = gz_curve_true(hull, draft, KG, angles)
    _, kn_true = kn_curve_true(hull, draft, KG, angles) \
                 if not args.no_heeled else (angles, gz_ws + KG * np.sin(np.radians(angles)))
    params = stability_parameters(ang_true, gz_true, hs.GM)
    print_stability(ang_true, gz_true, ang_ws, gz_ws, kn_true, params)

    # ── IMO stability check ───────────────────────────────────────────────
    imo_check = None
    if args.imo or args.report:
        imo_check = imo_intact_stability_check(params)
        print()
        print(imo_format(imo_check))

    # ── Trim solve ────────────────────────────────────────────────────────
    trim_result = None
    if args.trim:
        W, LCG = (float(x) for x in args.trim.split(","))
        _hdr("EQUILIBRIUM TRIM SOLUTION")
        trim_result = solve_equilibrium(hull, W=W, LCG=LCG, KG=KG)
        _row("Required displacement W",    f"{W:.2f}",                    "t")
        _row("Required LCG (from AP)",     f"{LCG:.3f}",                  "m")
        _row("Solved mean draft T_m",      f"{trim_result['T_mean']:.4f}", "m")
        _row("Solved trim (+ by bow)",     f"{trim_result['trim_m']:.4f}", "m")
        _row("Draft at FP",                f"{trim_result['T_F']:.4f}",   "m")
        _row("Draft at AP",                f"{trim_result['T_A']:.4f}",   "m")
        _row("Iterations",                 f"{trim_result['iter']}",       "")
        _row("Residual Δ",                 f"{trim_result['residual_W']:.3e}", "t")
        _row("Residual LCG",               f"{trim_result['residual_LCG']:.3e}", "m")

    # ── Weather criterion ─────────────────────────────────────────────────
    weather_result = None
    if args.weather:
        Aw_prof = 0.8 * hull.L * (hull.D - draft + 3.0)    # rough estimate
        Z       = 0.5 * (hull.D - draft) + 0.5 * draft
        weather_result = weather_criterion(
            displacement_t = hs.displacement,
            Aw_profile_m2  = Aw_prof,
            Z_m            = Z,
            gz_angles_deg  = ang_true,
            gz_values_m    = gz_true,
            OG_m           = KG - draft,
            draft_m        = draft,
        )
        _hdr("WEATHER CRITERION (A.749 §2.3)")
        for k, v in weather_result.items():
            print(f"  {k:<20}{v}")

    # ── Hydrostatic table ─────────────────────────────────────────────────
    table = None
    if args.table or args.report:
        draft_list = np.arange(0.2 * hull.D, hull.D + 1e-6, 0.1 * hull.D)
        table = hydrostatic_table(hull, list(draft_list), KG=KG)
        if args.table:
            print_hydrostatic_table(table)

    # ── Plots ─────────────────────────────────────────────────────────────
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    figure_paths = {}

    if not args.no_plot:
        import matplotlib.pyplot as plt
        tag  = hull.name.replace(" ", "_")
        save = args.save or args.report

        def _save(key, name):
            if save:
                figure_paths[key] = str(out_dir / f"{tag}_{name}")
                return figure_paths[key]
            return None

        print("\n  Generating figures …")
        plots.plot_body_plan(hull, draft, ship_name=hull.name,
                             save_path=_save("body_plan", "body_plan.png"))
        plots.plot_gz_curve(ang_true, gz_true, ang_ws, gz_ws, params,
                            ship_name=hull.name,
                            save_path=_save("gz", "GZ.png"))
        if table:
            plots.plot_hydrostatic_curves(table, ship_name=hull.name,
                                          save_path=_save("curves", "curves_of_form.png"))
        bj = bonjean_curves(hull, dT=0.2)
        plots.plot_bonjean(bj, ship_name=hull.name,
                           save_path=_save("bonjean", "bonjean.png"))
        if imo_check:
            plots.plot_imo_criteria(imo_check, ship_name=hull.name,
                                    save_path=_save("imo", "imo.png"))
        plots.plot_dashboard(hull, hs, ang_true, gz_true, ang_ws, gz_ws,
                             params, imo_check, ship_name=hull.name,
                             save_path=_save("dashboard", "dashboard.png"))

        if not save:
            plt.show()

    # ── PDF report ────────────────────────────────────────────────────────
    if args.report and imo_check:
        from hydro.report import generate_pdf
        pdf_path = out_dir / f"{hull.name.replace(' ', '_')}_report.pdf"
        summary["KG_m"] = KG
        generate_pdf(pdf_path,
                     ship_name     = hull.name,
                     hydro_summary = summary,
                     stab_params   = params,
                     imo_check     = imo_check,
                     figure_paths  = figure_paths,
                     weather       = weather_result,
                     trim_result   = trim_result)
        print(f"\n  PDF report written: {pdf_path}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
