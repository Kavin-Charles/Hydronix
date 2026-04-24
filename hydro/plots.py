"""
Publication-quality matplotlib figures for the hackathon report.

Color palette and styling are consistent across all plots.  Every
function accepts an optional `save_path` and returns the Figure so the
caller can further customise or embed into a PDF report.
"""

from __future__ import annotations

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import AutoMinorLocator
from typing import List, Optional, Tuple

matplotlib.rcParams.update({
    "font.family"      : "DejaVu Sans",
    "font.size"        : 10,
    "axes.grid"        : True,
    "grid.alpha"       : 0.28,
    "grid.linestyle"   : "-",
    "axes.titleweight" : "bold",
    "axes.spines.top"  : False,
    "axes.spines.right": False,
    "figure.dpi"       : 110,
})

BLUE, RED, GREEN, ORANGE, PURPLE, GREY = (
    "#1f6aa5", "#c0392b", "#27ae60", "#e67e22", "#8e44ad", "#7f8c8d"
)


# ---------------------------------------------------------------------------
# GZ curve – supports both wall-sided and true curves on the same axes
# ---------------------------------------------------------------------------

def plot_gz_curve(
    angles_true  : np.ndarray,
    gz_true      : np.ndarray,
    angles_ws    : Optional[np.ndarray] = None,
    gz_ws        : Optional[np.ndarray] = None,
    params       : Optional[dict]       = None,
    ship_name    : str                  = "Ship",
    save_path    : Optional[str]        = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 5.5))

    valid = ~np.isnan(gz_true)
    ax.plot(angles_true[valid], gz_true[valid],
            color=BLUE, linewidth=2.4, label="GZ – true (polygon-clipping)")
    ax.fill_between(angles_true[valid], 0, gz_true[valid],
                    where=gz_true[valid] >= 0, alpha=0.10, color=BLUE)
    ax.fill_between(angles_true[valid], 0, gz_true[valid],
                    where=gz_true[valid] <  0, alpha=0.10, color=RED)

    if angles_ws is not None and gz_ws is not None:
        v = ~np.isnan(gz_ws)
        ax.plot(angles_ws[v], gz_ws[v], color=RED, linestyle="--",
                linewidth=1.4, label="GZ – wall-sided (small-angle benchmark)")

    if params:
        gm = params.get("GM_m", 0.0)
        slope = np.linspace(0, min(10, angles_true[-1]), 40)
        ax.plot(slope, np.radians(slope) * gm, color=GREY,
                linestyle=":", linewidth=1.2,
                label=f"Initial slope = GM ({gm:.3f} m)")
        amax = params.get("angle_max_GZ_deg", float("nan"))
        gmax = params.get("max_GZ_m",         float("nan"))
        if not np.isnan(gmax):
            ax.annotate(f"GZmax = {gmax:.3f} m @ {amax:.1f}°",
                        xy=(amax, gmax), xytext=(amax + 6, gmax * 0.9),
                        arrowprops=dict(arrowstyle="->", color=BLUE),
                        color=BLUE, fontsize=9)
        avs = params.get("angle_vanishing_deg", float("nan"))
        if not np.isnan(avs):
            ax.axvline(avs, color=RED, linestyle="--", linewidth=1.0,
                       label=f"AVS = {avs:.1f}°")

    ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax.set_xlabel("Heel angle φ (°)")
    ax.set_ylabel("Righting lever GZ (m)")
    ax.set_title(f"{ship_name} – Static Stability (GZ) Curve")
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    ax.yaxis.set_minor_locator(AutoMinorLocator(5))
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------

def plot_kn_curves(
    angles       : np.ndarray,
    kn_matrix    : List[List[float]],          # [n_drafts][n_angles]
    displacements: List[float],
    ship_name    : str = "Ship",
    save_path    : Optional[str] = None,
) -> plt.Figure:
    """Cross-curves of stability: KN vs heel for each displacement."""
    fig, ax = plt.subplots(figsize=(10, 5.5))
    cmap = plt.cm.viridis
    for k, kn in enumerate(kn_matrix):
        c = cmap(k / max(len(kn_matrix) - 1, 1))
        ax.plot(angles, kn, color=c, linewidth=1.8,
                label=f"Δ = {displacements[k]:.0f} t")
    ax.set_xlabel("Heel angle φ (°)")
    ax.set_ylabel("KN (m)")
    ax.set_title(f"{ship_name} – Cross Curves of Stability (KN)")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------

def plot_body_plan(hull, draft: float, ship_name: str = "Ship",
                   save_path: Optional[str] = None) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 6.5))
    n_sta = len(hull.stations)
    mid   = n_sta // 2
    cmap  = plt.cm.cool

    for i in range(n_sta):
        color = cmap(i / max(n_sta - 1, 1))
        y = hull.half_breadths[i]
        z = hull.waterlines
        if i <= mid:                  # aft half → port side
            ax.plot(-y, z, color=color, linewidth=1.3)
        if i >= mid:                  # fore half → starboard side
            ax.plot(y, z, color=color, linewidth=1.3)

    for z in hull.waterlines:
        ax.axhline(z, color=BLUE, linewidth=0.4, alpha=0.25)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.axhline(draft, color=RED, linestyle="--",
               linewidth=1.3, label=f"Design draft T = {draft:.2f} m")
    ax.fill_between([-hull.B_max, hull.B_max], 0, draft,
                    color=BLUE, alpha=0.05)

    ax.set_xlabel("Half-breadth (m)       ← Port    |    Stbd →")
    ax.set_ylabel("Height above keel (m)")
    ax.set_title(f"{ship_name} – Body Plan")
    ax.legend(fontsize=8)
    ax.set_aspect("equal")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------

def plot_hydrostatic_curves(table: List[dict], ship_name: str = "Ship",
                            save_path: Optional[str] = None) -> plt.Figure:
    keys = ["draft_m", "displacement_t", "waterplane_area_m2",
            "KB_m", "BM_m", "KM_m", "GM_m",
            "lcb_from_ap_m", "lcf_from_ap_m", "Cb", "Cw", "TPC_t_per_cm"]
    T   = np.array([r["draft_m"]                for r in table])
    D   = np.array([r["displacement_t"]         for r in table])
    Aw  = np.array([r["waterplane_area_m2"]     for r in table])
    KB  = np.array([r["KB_m"]                   for r in table])
    BM  = np.array([r["BM_m"]                   for r in table])
    KM  = np.array([r["KM_m"]                   for r in table])
    GM  = np.array([r["GM_m"]                   for r in table])
    LCB = np.array([r["lcb_from_ap_m"]          for r in table])
    LCF = np.array([r["lcf_from_ap_m"]          for r in table])
    Cb  = np.array([r["Cb"]                     for r in table])
    TPC = np.array([r["TPC_t_per_cm"]           for r in table])

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle(f"{ship_name} – Curves of Form (hydrostatic particulars vs draft)",
                 fontsize=13, fontweight="bold")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.32)

    def _sub(pos, x, y, xlabel, title, color):
        ax = fig.add_subplot(pos)
        ax.plot(x, y, color=color, linewidth=2)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel("Draft T (m)", fontsize=9)
        ax.set_title(title, fontsize=10)
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())

    _sub(gs[0, 0], D,  T, "Displacement Δ (t)",    "Displacement",        BLUE)
    _sub(gs[0, 1], Aw, T, "Waterplane area (m²)",  "Waterplane Area",     ORANGE)
    _sub(gs[0, 2], TPC, T, "TPC (t/cm)",           "Tonnes per cm",       PURPLE)

    # Metacentric quantities
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(KB, T, color=GREEN,  linewidth=2, label="KB")
    ax4.plot(BM, T, color=ORANGE, linewidth=2, label="BM")
    ax4.plot(KM, T, color=BLUE,   linewidth=2, label="KM")
    ax4.plot(GM, T, color=RED,    linewidth=2, label="GM")
    ax4.set_xlabel("Height (m)"); ax4.set_ylabel("Draft T (m)")
    ax4.set_title("Metacentric Heights"); ax4.legend(fontsize=8)

    # Longitudinal centres
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.plot(LCB, T, color=BLUE,  linewidth=2, label="LCB")
    ax5.plot(LCF, T, color=GREEN, linewidth=2, linestyle="--", label="LCF")
    ax5.set_xlabel("Distance from AP (m)"); ax5.set_ylabel("Draft T (m)")
    ax5.set_title("LCB & LCF"); ax5.legend(fontsize=8)

    _sub(gs[1, 2], Cb, T, "Block coefficient Cb", "Block Coefficient", GREY)

    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------

def plot_bonjean(data: dict, ship_name: str = "Ship",
                 save_path: Optional[str] = None) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6))
    cmap = plt.cm.plasma
    for i, x in enumerate(data["stations"]):
        c = cmap(i / max(len(data["stations"]) - 1, 1))
        ax.plot(data["area"][i], data["drafts"], color=c, linewidth=1.2,
                label=f"St {i}" if i % max(1, len(data['stations']) // 6) == 0 else None)
    ax.set_xlabel("Section area (m²)")
    ax.set_ylabel("Draft T (m)")
    ax.set_title(f"{ship_name} – Bonjean Curves")
    ax.legend(fontsize=7, loc="lower right", ncol=2)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------

def plot_imo_criteria(check: dict, ship_name: str = "Ship",
                      save_path: Optional[str] = None) -> plt.Figure:
    """Horizontal bar chart: actual vs limit for each IMO criterion."""
    crits = check["criteria"]
    labels   = [c["description"][:40] for c in crits]
    actuals  = [c["actual"]           for c in crits]
    limits   = [c["limit"]            for c in crits]
    statuses = [c["status"]           for c in crits]

    fig, ax = plt.subplots(figsize=(10, 0.55 * len(crits) + 2.5))
    y = np.arange(len(labels))
    colors = [GREEN if s == "PASS" else (RED if s == "FAIL" else GREY)
              for s in statuses]
    # Normalised bars: actual / limit
    norms = [(a / l) if (l != 0 and not np.isnan(a)) else 0.0
             for a, l in zip(actuals, limits)]
    ax.barh(y, norms, color=colors, edgecolor="black", linewidth=0.5)
    ax.axvline(1.0, color="black", linestyle="--", linewidth=1.2, label="IMO limit")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Actual / Limit   (≥ 1.0 to pass)")
    ax.set_title(f"{ship_name} – IMO 2008 IS Code Intact-Stability Criteria  "
                 f"[{check['overall']}]")
    # Annotate each bar
    for i, (a, l, s) in enumerate(zip(actuals, limits, statuses)):
        txt = f"{a:.4f} / {l:.3f}"
        ax.text(max(norms[i], 0.02) + 0.05, i, f"{txt}  {s}",
                va="center", fontsize=7.5)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig


# ---------------------------------------------------------------------------
# Dashboard – single-page executive summary
# ---------------------------------------------------------------------------

def plot_dashboard(
    hull,
    hs,                                     # Hydrostatics
    ang_true, gz_true,
    ang_ws,   gz_ws,
    params,
    imo_check : Optional[dict] = None,
    ship_name : str = "Ship",
    save_path : Optional[str] = None,
) -> plt.Figure:
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(
        f"{ship_name}   |   T = {hs.draft:.2f} m   |   "
        f"Δ = {hs.displacement:.1f} t   |   GM = {hs.GM:.3f} m",
        fontsize=14, fontweight="bold")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.32)

    # --- body plan
    ax0 = fig.add_subplot(gs[0, 0])
    n_sta = len(hull.stations); mid = n_sta // 2
    cmap = plt.cm.cool
    for i in range(n_sta):
        c = cmap(i / max(n_sta - 1, 1))
        if i <= mid:
            ax0.plot(-hull.half_breadths[i], hull.waterlines, color=c, linewidth=1.2)
        if i >= mid:
            ax0.plot( hull.half_breadths[i], hull.waterlines, color=c, linewidth=1.2)
    ax0.axhline(hs.draft, color=RED, linestyle="--", linewidth=1.0,
                label=f"T = {hs.draft} m")
    ax0.axvline(0, color="black", linewidth=0.7)
    ax0.set_aspect("equal"); ax0.set_title("Body Plan", fontsize=10)
    ax0.set_xlabel("y (m)"); ax0.set_ylabel("z (m)"); ax0.legend(fontsize=7)

    # --- GZ
    ax1 = fig.add_subplot(gs[0, 1])
    v = ~np.isnan(gz_true)
    ax1.plot(ang_true[v], gz_true[v], color=BLUE, linewidth=2.2, label="True (polygon)")
    if ang_ws is not None and gz_ws is not None:
        vw = ~np.isnan(gz_ws)
        ax1.plot(ang_ws[vw], gz_ws[vw], color=RED, linestyle="--",
                 linewidth=1.3, label="Wall-sided")
    slope = np.linspace(0, 10, 30)
    ax1.plot(slope, np.radians(slope) * hs.GM, color=GREY, linestyle=":",
             linewidth=1, label="GM slope")
    ax1.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax1.set_xlabel("φ (°)"); ax1.set_ylabel("GZ (m)")
    ax1.set_title("GZ Curve", fontsize=10); ax1.legend(fontsize=7)

    # --- IMO criteria summary
    ax2 = fig.add_subplot(gs[0, 2])
    if imo_check:
        crits = imo_check["criteria"]
        y = np.arange(len(crits))
        norms  = [(c["actual"] / c["limit"]) if c["limit"] else 0 for c in crits]
        colors = [GREEN if c["status"] == "PASS" else RED for c in crits]
        ax2.barh(y, norms, color=colors, edgecolor="black", linewidth=0.4)
        ax2.axvline(1.0, color="black", linestyle="--", linewidth=1)
        ax2.set_yticks(y)
        ax2.set_yticklabels([c["description"][:28] for c in crits], fontsize=7)
        ax2.set_xlabel("Actual / Limit")
        ax2.set_title(f"IMO A.749  [{imo_check['overall']}]", fontsize=10)
    else:
        ax2.axis("off")

    # --- Hydrostatic summary table
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.axis("off")
    s = hs.summary()
    rows = [
        ("Parameter",        "Value",                        "Unit"),
        ("─" * 24,           "─" * 10,                       "─" * 6),
        ("Displacement ∇",   f"{s['displacement_m3']:.2f}",  "m³"),
        ("Displacement Δ",   f"{s['displacement_t']:.2f}",   "t"),
        ("Waterplane Aw",    f"{s['waterplane_area_m2']:.2f}","m²"),
        ("LCB from AP",      f"{s['lcb_from_ap_m']:.3f}",   "m"),
        ("LCF from AP",      f"{s['lcf_from_ap_m']:.3f}",   "m"),
        ("KB",               f"{s['KB_m']:.3f}",             "m"),
        ("BM",               f"{s['BM_m']:.3f}",             "m"),
        ("KM",               f"{s['KM_m']:.3f}",             "m"),
        ("GM",               f"{s['GM_m']:.3f}",             "m"),
        ("BML",              f"{s['BML_m']:.3f}",            "m"),
        ("GML",              f"{s['GML_m']:.3f}",            "m"),
        ("Cb",               f"{s['Cb']:.4f}",               "–"),
        ("Cw",               f"{s['Cw']:.4f}",               "–"),
        ("Cm",               f"{s['Cm']:.4f}",               "–"),
        ("Cp",               f"{s['Cp']:.4f}",               "–"),
        ("TPC",              f"{s['TPC_t_per_cm']:.3f}",     "t/cm"),
        ("MCTC",             f"{s['MCTC_tm_per_cm']:.3f}",   "t·m/cm"),
    ]
    y = 0.98
    for row in rows:
        for xi, cell in zip((0.0, 0.60, 0.86), row):
            fw = "bold" if row[0] == "Parameter" else "normal"
            ax3.text(xi, y, cell, transform=ax3.transAxes,
                     fontsize=8.5, va="top", fontweight=fw, fontfamily="monospace")
        y -= 0.052

    # --- Stability parameters table
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis("off")
    p = params or {}
    srows = [
        ("Metric",           "Value",                          "Unit"),
        ("─" * 24,           "─" * 10,                         "─" * 6),
        ("GZ at 30°",        f"{p.get('GZ_at_30deg_m', float('nan')):.4f}",    "m"),
        ("GZ at 40°",        f"{p.get('GZ_at_40deg_m', float('nan')):.4f}",    "m"),
        ("Max GZ",           f"{p.get('max_GZ_m', float('nan')):.4f}",         "m"),
        ("Angle of max GZ",  f"{p.get('angle_max_GZ_deg', float('nan')):.2f}", "°"),
        ("Area 0 → 30°",     f"{p.get('area_0_30_m_rad', float('nan')):.5f}",  "m·rad"),
        ("Area 0 → 40°",     f"{p.get('area_0_40_m_rad', float('nan')):.5f}",  "m·rad"),
        ("Area 30° → 40°",   f"{p.get('area_30_40_m_rad', float('nan')):.5f}", "m·rad"),
        ("Angle vanishing",  f"{p.get('angle_vanishing_deg', float('nan')):.2f}", "°"),
    ]
    y = 0.98
    for row in srows:
        for xi, cell in zip((0.0, 0.55, 0.82), row):
            fw = "bold" if row[0] == "Metric" else "normal"
            ax4.text(xi, y, cell, transform=ax4.transAxes,
                     fontsize=8.5, va="top", fontweight=fw, fontfamily="monospace")
        y -= 0.062

    # --- KN curve
    ax5 = fig.add_subplot(gs[1, 2])
    kn = gz_true + hs.KG * np.sin(np.radians(ang_true))
    v = ~np.isnan(kn)
    ax5.plot(ang_true[v], kn[v], color=GREEN, linewidth=2)
    ax5.axhline(0, color="black", linewidth=0.7, linestyle="--")
    ax5.set_xlabel("φ (°)"); ax5.set_ylabel("KN (m)")
    ax5.set_title("KN Curve (righting lever from keel)", fontsize=10)

    if save_path:
        fig.savefig(save_path, dpi=170, bbox_inches="tight")
    return fig
