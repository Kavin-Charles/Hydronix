"""
Automated PDF stability report (reportlab)
==========================================

Produces a multi-page, professionally-formatted PDF containing:

  1. Cover page with principal particulars
  2. Hydrostatic summary table
  3. Curves of form (figure)
  4. Body plan
  5. GZ curve (true + wall-sided)
  6. IMO stability criteria check (tabular + bar chart)
  7. Optional: Bonjean curves

Image files are embedded directly, so the caller is responsible for having
generated them first (`hydro.plots.*(..., save_path=...)`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units    import cm
from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
from reportlab.lib          import colors
from reportlab.platypus     import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak, Image)


# ---------------------------------------------------------------------------

def _kv_table(pairs, col_widths=(8 * cm, 6 * cm)):
    t = Table(pairs, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT",       (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT",       (0, 0), (0, -1),  "Helvetica-Bold", 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.lightgrey),
    ]))
    return t


def _criteria_table(criteria):
    data = [["Criterion", "Limit", "Actual", "Status"]]
    for c in criteria:
        actual = f"{c['actual']:.4f}" if c['actual'] == c['actual'] else "N/A"
        data.append([c["description"][:60], f"{c['limit']:.3f}",
                     actual, c["status"]])
    t = Table(data, colWidths=(9.5 * cm, 2 * cm, 2.2 * cm, 1.8 * cm),
              repeatRows=1)
    style = [
        ("FONT",          (0, 0), (-1,  0), "Helvetica-Bold", 9),
        ("FONT",          (0, 1), (-1, -1), "Helvetica",      9),
        ("BACKGROUND",    (0, 0), (-1,  0), colors.HexColor("#1f6aa5")),
        ("TEXTCOLOR",     (0, 0), (-1,  0), colors.white),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.grey),
        ("ALIGN",         (1, 1), (-1, -1), "CENTER"),
    ]
    for i, c in enumerate(criteria, 1):
        bg = colors.HexColor("#e8f5e9") if c["status"] == "PASS" \
             else colors.HexColor("#ffebee")
        style.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------

def generate_pdf(
    output_path   : str | Path,
    ship_name     : str,
    hydro_summary : Dict,
    stab_params   : Dict,
    imo_check     : Dict,
    figure_paths  : Dict[str, str],     # keys: body_plan, gz, curves, bonjean, imo
    weather       : Optional[Dict] = None,
    trim_result   : Optional[Dict] = None,
) -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Sub", parent=styles["Heading3"],
                              textColor=colors.HexColor("#1f6aa5")))

    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=f"{ship_name} – Stability Report",
                            author="HydroHackathon")

    flow = []

    # ── Cover ────────────────────────────────────────────────────────────
    flow.append(Paragraph(f"<b>HydroHackathon 2026</b>", styles["Title"]))
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph(f"Ship Stability Report – <b>{ship_name}</b>",
                          styles["Heading2"]))
    flow.append(Spacer(1, 0.4 * cm))

    cover = [
        ("Length (between perpendiculars)", f"{hydro_summary['L_m']:.2f} m"),
        ("Maximum moulded breadth",         f"{hydro_summary['B_max_m']:.2f} m"),
        ("Moulded depth",                   f"{hydro_summary['D_m']:.2f} m"),
        ("Design draft T",                  f"{hydro_summary['draft_m']:.3f} m"),
        ("Fluid density ρ",                 f"{hydro_summary['rho_t_per_m3']:.3f} t/m³"),
        ("Vertical centre of gravity KG",   f"{hydro_summary['KG_m']:.3f} m"),
    ]
    flow.append(_kv_table(cover))
    flow.append(Spacer(1, 0.6 * cm))

    # ── Hydrostatic summary ──────────────────────────────────────────────
    flow.append(Paragraph("1. Hydrostatic Particulars", styles["Heading2"]))
    hs_rows = [
        ("Displacement volume ∇",           f"{hydro_summary['displacement_m3']:.3f} m³"),
        ("Displacement Δ",                  f"{hydro_summary['displacement_t']:.3f} t"),
        ("Waterplane area Aw",              f"{hydro_summary['waterplane_area_m2']:.3f} m²"),
        ("Midship section area Am",         f"{hydro_summary['Am_m2']:.3f} m²"),
        ("LCB from AP",                     f"{hydro_summary['lcb_from_ap_m']:.4f} m"),
        ("LCF from AP",                     f"{hydro_summary['lcf_from_ap_m']:.4f} m"),
        ("KB",                              f"{hydro_summary['KB_m']:.4f} m"),
        ("BM  (IT/∇)",                      f"{hydro_summary['BM_m']:.4f} m"),
        ("KM  (KB+BM)",                     f"{hydro_summary['KM_m']:.4f} m"),
        ("GM  (KM−KG)",                     f"{hydro_summary['GM_m']:.4f} m"),
        ("BML (IL/∇)",                      f"{hydro_summary['BML_m']:.4f} m"),
        ("GML (KB+BML−KG)",                 f"{hydro_summary['GML_m']:.4f} m"),
        ("TPC",                             f"{hydro_summary['TPC_t_per_cm']:.3f} t/cm"),
        ("MCTC",                            f"{hydro_summary['MCTC_tm_per_cm']:.3f} t·m/cm"),
        ("Block coefficient Cb",            f"{hydro_summary['Cb']:.4f}"),
        ("Waterplane coefficient Cw",       f"{hydro_summary['Cw']:.4f}"),
        ("Midship coefficient Cm",          f"{hydro_summary['Cm']:.4f}"),
        ("Prismatic coefficient Cp",        f"{hydro_summary['Cp']:.4f}"),
    ]
    flow.append(_kv_table(hs_rows))
    flow.append(Spacer(1, 0.3 * cm))

    if "curves" in figure_paths and Path(figure_paths["curves"]).exists():
        flow.append(Paragraph("2. Curves of Form", styles["Heading2"]))
        flow.append(Image(figure_paths["curves"], width=16 * cm, height=11 * cm))
        flow.append(PageBreak())

    if "body_plan" in figure_paths and Path(figure_paths["body_plan"]).exists():
        flow.append(Paragraph("3. Body Plan", styles["Heading2"]))
        flow.append(Image(figure_paths["body_plan"], width=14 * cm, height=10 * cm))
        flow.append(Spacer(1, 0.4 * cm))

    # ── Stability ──
    flow.append(Paragraph("4. Stability – GZ Curve", styles["Heading2"]))
    if "gz" in figure_paths and Path(figure_paths["gz"]).exists():
        flow.append(Image(figure_paths["gz"], width=16 * cm, height=9 * cm))
    stab_rows = [
        ("Initial GM",                 f"{stab_params['GM_m']:.4f} m"),
        ("GZ at 30°",                  f"{stab_params['GZ_at_30deg_m']:.4f} m"),
        ("GZ at 40°",                  f"{stab_params['GZ_at_40deg_m']:.4f} m"),
        ("Maximum GZ",                 f"{stab_params['max_GZ_m']:.4f} m"),
        ("Heel at max GZ",             f"{stab_params['angle_max_GZ_deg']:.2f} °"),
        ("Area  0 → 30°",              f"{stab_params['area_0_30_m_rad']:.5f} m·rad"),
        ("Area  0 → 40°",              f"{stab_params['area_0_40_m_rad']:.5f} m·rad"),
        ("Area 30° → 40°",             f"{stab_params['area_30_40_m_rad']:.5f} m·rad"),
        ("Angle of vanishing stability", f"{stab_params['angle_vanishing_deg']:.2f} °"),
    ]
    flow.append(Spacer(1, 0.2 * cm))
    flow.append(_kv_table(stab_rows))
    flow.append(PageBreak())

    # ── IMO ──
    flow.append(Paragraph("5. IMO 2008 IS Code – Intact Stability Criteria",
                          styles["Heading2"]))
    flow.append(Paragraph(
        f"<b>Overall verdict: {imo_check['overall']}</b> "
        f"({imo_check['passed']} passed / {imo_check['failed']} failed).",
        styles["Normal"]))
    flow.append(Spacer(1, 0.3 * cm))
    flow.append(_criteria_table(imo_check["criteria"]))
    flow.append(Spacer(1, 0.4 * cm))
    if "imo" in figure_paths and Path(figure_paths["imo"]).exists():
        flow.append(Image(figure_paths["imo"], width=16 * cm, height=7 * cm))

    # ── Weather ──
    if weather is not None:
        flow.append(PageBreak())
        flow.append(Paragraph("6. Severe Wind-and-Rolling (Weather) Criterion",
                              styles["Heading2"]))
        w_rows = [
            ("Wind-heeling lever lw1",      f"{weather['lw1']:.4f} m"),
            ("Gust lever lw2",              f"{weather['lw2']:.4f} m"),
            ("Equilibrium heel φ₀",          f"{weather['phi0_deg']:.2f} °"),
            ("Roll-back angle φ₁",           f"{weather['phi1_deg']:.2f} °"),
            ("Righting area b (m·rad)",     f"{weather['area_b_m_rad']:.4f}"),
            ("Wind energy a (m·rad)",       f"{weather['area_a_m_rad']:.4f}"),
            ("Verdict",                     "PASS" if weather["pass"] else "FAIL"),
        ]
        flow.append(_kv_table(w_rows))

    # ── Trim ──
    if trim_result is not None:
        flow.append(PageBreak())
        flow.append(Paragraph("7. Equilibrium Trim Solution", styles["Heading2"]))
        tr_rows = [
            ("Mean draft T_m",              f"{trim_result['T_mean']:.3f} m"),
            ("Trim  (+ by bow)",            f"{trim_result['trim_m']:.4f} m"),
            ("Draft at FP",                 f"{trim_result['T_F']:.3f} m"),
            ("Draft at AP",                 f"{trim_result['T_A']:.3f} m"),
            ("Iterations",                  str(trim_result["iter"])),
            ("Residual Δ (t)",              f"{trim_result['residual_W']:.3e}"),
            ("Residual LCG (m)",            f"{trim_result['residual_LCG']:.3e}"),
        ]
        flow.append(_kv_table(tr_rows))

    doc.build(flow)
