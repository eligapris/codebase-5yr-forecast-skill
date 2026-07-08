#!/usr/bin/env python3
"""
generate_report.py — PDF + JSON bundle generator for the codebase-5yr-forecast skill.

Reads:
  - scores.json (from moat_calculator.py)
  - scan.json (from codebase_scanner.py)
  - evidence.json (gathered by the LLM in Phase 3)
  - scoring_input.json (the LLM's input to the calculator)
  - narrative.json (optional, the LLM's prose sections)

Writes to /home/z/my-project/download/:
  - <project_slug>_5yr_forecast.pdf
  - <project_slug>_5yr_forecast.json

Usage:
    python generate_report.py \\
        --scores scores.json \\
        --scan scan.json \\
        --evidence evidence.json \\
        --scoring-input scoring_input.json \\
        --narrative narrative.json \\
        --output-dir /home/z/my-project/download/
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# matplotlib for charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

# ReportLab for PDF
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether,
)
from reportlab.pdfgen import canvas


SCRIPT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Font setup (per system rules)
# ---------------------------------------------------------------------------

def setup_fonts():
    """Register Chinese-capable fonts for matplotlib per-glyph fallback."""
    try:
        fm.fontManager.addfont('/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf')
    except Exception:
        pass
    try:
        fm.fontManager.addfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    except Exception:
        pass
    plt.rcParams['font.sans-serif'] = ['Noto Sans SC', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

ACCENT = colors.HexColor("#1f4e79")
ACCENT_LIGHT = colors.HexColor("#d6e4f0")
DANGER = colors.HexColor("#c0392b")
WARNING = colors.HexColor("#e67e22")
SUCCESS = colors.HexColor("#27ae60")
GRAY_DARK = colors.HexColor("#333333")
GRAY_LIGHT = colors.HexColor("#f5f5f5")


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle("cover_title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=28, leading=34, textColor=ACCENT, alignment=TA_CENTER, spaceAfter=12),
        "cover_subtitle": ParagraphStyle("cover_subtitle", parent=base["Normal"],
            fontName="Helvetica", fontSize=14, leading=18, textColor=GRAY_DARK, alignment=TA_CENTER, spaceAfter=8),
        "verdict_huge": ParagraphStyle("verdict_huge", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=22, leading=28, alignment=TA_CENTER, spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=ACCENT, spaceAfter=10, spaceBefore=14),
        "h2": ParagraphStyle("h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ACCENT, spaceAfter=6, spaceBefore=10),
        "body": ParagraphStyle("body", parent=base["Normal"],
            fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT, spaceAfter=6),
        "body_bold": ParagraphStyle("body_bold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=10, leading=14, alignment=TA_LEFT, spaceAfter=6),
        "small": ParagraphStyle("small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, leading=11, textColor=GRAY_DARK, alignment=TA_LEFT),
        "small_italic": ParagraphStyle("small_italic", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=8, leading=11, textColor=GRAY_DARK),
        "mono": ParagraphStyle("mono", parent=base["Normal"],
            fontName="Courier", fontSize=9, leading=12),
        "table_cell": ParagraphStyle("table_cell", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=12),
        "table_header": ParagraphStyle("table_header", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white),
    }
    return styles


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def verdict_color(verdict: str):
    if "Durable" in verdict:
        return SUCCESS
    if "Eroding" in verdict:
        return WARNING
    return DANGER


def make_decay_curve_chart(scores: dict, output_path: Path):
    """Line chart: M(t) over 5 years, with bull/base/bear overlay."""
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    years = [p["year"] for p in scores["composite"]["base_projection"]]
    base = [p["moat_score"] for p in scores["composite"]["base_projection"]]
    bull = [p["moat_score"] for p in scores["scenarios"]["bull"]["projection"]]
    bear = [p["moat_score"] for p in scores["scenarios"]["bear"]["projection"]]

    ax.plot(years, bull, color="#27ae60", linewidth=2, marker="o", label="Bull (25%)")
    ax.plot(years, base, color="#2980b9", linewidth=2.5, marker="s", label="Base (50%)")
    ax.plot(years, bear, color="#c0392b", linewidth=2, marker="^", label="Bear (25%)")

    # Shade between bull and bear
    ax.fill_between(years, bear, bull, color="#7f8c8d", alpha=0.15)

    # Verdict thresholds
    ax.axhline(y=70, color="#27ae60", linestyle="--", alpha=0.4, linewidth=1)
    ax.axhline(y=50, color="#e67e22", linestyle="--", alpha=0.4, linewidth=1)
    ax.axhline(y=30, color="#c0392b", linestyle="--", alpha=0.4, linewidth=1)

    ax.text(5.1, 70, " Durable", fontsize=8, va="center", color="#27ae60")
    ax.text(5.1, 50, " Eroding", fontsize=8, va="center", color="#e67e22")
    ax.text(5.1, 30, " At Risk", fontsize=8, va="center", color="#c0392b")

    ax.set_xlabel("Year (from now)")
    ax.set_ylabel("Moat Durability Score (0-100)")
    ax.set_title("5-Year Moat Decay Projection — Bull / Base / Bear Scenarios", fontsize=11, fontweight="bold")
    ax.set_xlim(-0.2, 6.5)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(True, alpha=0.3)

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def make_radar_chart(scores: dict, output_path: Path):
    """Radar chart of the 4 axes."""
    axes_data = scores["axes"]
    labels = ["Technical\nMoat", "Trend\nAlignment", "Market\nDemand", "AI Disruption\n(inverted)"]
    values = [
        axes_data["technical_moat"]["axis_score"],
        axes_data["trend_alignment"]["axis_score"],
        axes_data["market_demand"]["axis_score"],
        100 - axes_data["ai_disruption_exposure"]["axis_score"],
    ]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values_loop = values + [values[0]]
    angles_loop = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True), constrained_layout=True)
    ax.plot(angles_loop, values_loop, color="#1f4e79", linewidth=2)
    ax.fill(angles_loop, values_loop, color="#1f4e79", alpha=0.25)

    # Reference polygon at 50
    ref = [50] * len(angles_loop)
    ax.plot(angles_loop, ref, color="#7f8c8d", linewidth=1, linestyle="--", alpha=0.5)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=7)
    ax.set_title("Moat Scorecard — 4 Axes", fontsize=11, fontweight="bold", pad=20)

    # Annotate values
    for angle, value, label in zip(angles, values, labels):
        ax.annotate(f"{value:.1f}", xy=(angle, value), fontsize=9, fontweight="bold",
                    ha="center", va="bottom", color="#1f4e79")

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def make_subscore_bar_chart(scores: dict, output_path: Path):
    """Horizontal bar chart of all sub-scores, grouped by axis."""
    axes_data = scores["axes"]
    rows = []

    for axis_name, label in [
        ("technical_moat", "Tech Moat"),
        ("trend_alignment", "Trend"),
        ("market_demand", "Market"),
        ("ai_disruption_exposure", "AI Exposure"),
    ]:
        axis = axes_data[axis_name]
        if "sub_scores_0_100" in axis:
            sub = axis["sub_scores_0_100"]
        else:
            sub = {k: v for k, v in axis["sub_scores"].items()
                   if isinstance(v, (int, float)) and k != "tam_cagr_pct"}
        for name, value in sub.items():
            rows.append((f"{label} · {name.replace('_', ' ')}", value, label))

    # Sort within axis by value descending
    rows.sort(key=lambda r: (r[2], -r[1]))

    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    colors_list = []
    color_map = {"Tech Moat": "#1f4e79", "Trend": "#2980b9", "Market": "#16a085", "AI Exposure": "#c0392b"}
    colors_list = [color_map[r[2]] for r in rows]

    fig, ax = plt.subplots(figsize=(9, max(4, len(rows) * 0.35)), constrained_layout=True)
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors_list, alpha=0.85)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score (0-100)")
    ax.set_title("Sub-Score Breakdown", fontsize=11, fontweight="bold")
    ax.axvline(x=50, color="#7f8c8d", linestyle="--", alpha=0.4)
    for i, v in enumerate(values):
        ax.text(v + 1, i, f"{v:.0f}", fontsize=7, va="center")
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.3)

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return s or "project"


def safe_text(s) -> str:
    """Escape XML special characters for ReportLab paragraphs."""
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_score(s) -> str:
    return f"{s:.1f}" if isinstance(s, (int, float)) else str(s)


def build_pdf(
    scores: dict,
    scan: dict | None,
    evidence: list | None,
    scoring_input: dict | None,
    narrative: dict | None,
    output_path: Path,
    chart_dir: Path,
):
    styles = build_styles()

    # Generate charts
    decay_chart = chart_dir / "decay_curve.png"
    radar_chart = chart_dir / "radar.png"
    subscore_chart = chart_dir / "subscores.png"
    make_decay_curve_chart(scores, decay_chart)
    make_radar_chart(scores, radar_chart)
    make_subscore_bar_chart(scores, subscore_chart)

    # Build document
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"{scores['project_name']} — 5-Year Forecast",
        author="codebase-5yr-forecast skill",
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=footer_callback)])

    story = []

    # ---- Cover page ----
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("5-Year Codebase Forecast", styles["cover_title"]))
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(safe_text(scores["project_name"]), styles["cover_subtitle"]))
    story.append(Spacer(1, 0.15 * inch))
    verdict = scores["verdict"]
    story.append(Paragraph(safe_text(verdict), styles["verdict_huge"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"Expected 5-Year Moat Score: <b>{scores['expected_y5']:.1f}</b> / 100",
        styles["cover_subtitle"]))
    story.append(Paragraph(
        f"Initial Moat Score (M0): <b>{scores['composite']['m0']:.1f}</b> / 100",
        styles["cover_subtitle"]))
    if scores.get("confidence_interval"):
        ci = scores["confidence_interval"]
        story.append(Paragraph(
            f"90% Confidence Interval (M0): <b>[{ci['p5']:.1f}, {ci['p95']:.1f}]</b>",
            styles["cover_subtitle"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        styles["small"]))
    story.append(Paragraph(
        f"Skill version: 1.0.0 · Script version: {scores.get('script_version', '1.0.0')}",
        styles["small"]))
    story.append(Paragraph(
        f"Input hash: <font face='Courier' size='7'>{scores.get('input_hash', '')}</font>",
        styles["small"]))

    story.append(PageBreak())

    # ---- Section 1: Executive Verdict ----
    story.append(Paragraph("1. Executive Verdict", styles["h1"]))

    verdict_table = Table([
        [Paragraph("<b>Verdict</b>", styles["table_cell"]),
         Paragraph(safe_text(verdict), styles["table_cell"])],
        [Paragraph("<b>Expected Y5 Score</b>", styles["table_cell"]),
         Paragraph(f"{scores['expected_y5']:.1f} / 100", styles["table_cell"])],
        [Paragraph("<b>Initial Score (M0)</b>", styles["table_cell"]),
         Paragraph(f"{scores['composite']['m0']:.1f} / 100", styles["table_cell"])],
        [Paragraph("<b>Annual Decay Rate (lambda)</b>", styles["table_cell"]),
         Paragraph(f"{scores['composite']['lambda']:.4f} ({scores['composite']['lambda']*100:.2f}% per year)", styles["table_cell"])],
        [Paragraph("<b>Dominant Risk Axis</b>", styles["table_cell"]),
         Paragraph(safe_text(_dominant_risk_axis(scores)), styles["table_cell"])],
    ], colWidths=[2.2 * inch, 4.3 * inch])
    verdict_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), GRAY_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(verdict_table)
    story.append(Spacer(1, 0.15 * inch))

    # Executive narrative (if provided)
    if narrative and narrative.get("executive_summary"):
        for para in narrative["executive_summary"]:
            story.append(Paragraph(safe_text(para), styles["body"]))
    else:
        story.append(Paragraph(
            f"Verdict derives from an algorithmic scoring of four axes (Technical Moat, Trend Alignment, "
            f"Market Demand, AI Disruption Exposure). The composite M0 score of <b>{scores['composite']['m0']:.1f}</b> "
            f"decays exponentially under an AI-disruption-driven lambda of <b>{scores['composite']['lambda']:.4f}</b>. "
            f"Under three scenarios (bull 25%, base 50%, bear 25%), the probability-weighted expected 5-year score is "
            f"<b>{scores['expected_y5']:.1f}</b>. This falls in the <b>{verdict}</b> band.",
            styles["body"]))
        story.append(Paragraph(
            "Scenario breakdown: "
            f"bull Y5 = {scores['scenarios']['bull']['y5_score']:.1f}, "
            f"base Y5 = {scores['scenarios']['base']['y5_score']:.1f}, "
            f"bear Y5 = {scores['scenarios']['bear']['y5_score']:.1f}.",
            styles["body"]))

    # Override notice
    if scores.get("overrides_applied"):
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            f"<b>NOTE:</b> {len(scores['overrides_applied'])} score override(s) were applied. "
            f"See Appendix B for details.",
            styles["small_italic"]))

    # Decay curve chart
    story.append(Spacer(1, 0.15 * inch))
    story.append(Image(str(decay_chart), width=6.5 * inch, height=3.65 * inch))

    # ---- Section 2: Moat Scorecard ----
    story.append(Paragraph("2. Moat Scorecard", styles["h1"]))
    story.append(Paragraph(
        "Four axes compose the composite Moat Durability Score. Each axis is a weighted average of sub-scores. "
        "Sub-score values are set by the LLM based on evidence; weights and the composite formula are fixed in "
        "<font face='Courier' size='8'>references/scoring-methodology.md</font> and applied deterministically by "
        "<font face='Courier' size='8'>moat_calculator.py</font>.",
        styles["body"]))

    # Radar chart
    story.append(Image(str(radar_chart), width=4.5 * inch, height=4.5 * inch))

    # Axis summary table
    axis_rows = [[
        Paragraph("<b>Axis</b>", styles["table_header"]),
        Paragraph("<b>Score</b>", styles["table_header"]),
        Paragraph("<b>Weight in Composite</b>", styles["table_header"]),
        Paragraph("<b>Direction</b>", styles["table_header"]),
    ]]
    axis_data = [
        ("Technical Moat", scores["axes"]["technical_moat"]["axis_score"], "30%", "higher = better"),
        ("Trend Alignment", scores["axes"]["trend_alignment"]["axis_score"], "20%", "higher = better"),
        ("Market & Demand", scores["axes"]["market_demand"]["axis_score"], "25%", "higher = better"),
        ("AI Disruption Exposure", scores["axes"]["ai_disruption_exposure"]["axis_score"], "25%", "lower = better (inverted)"),
    ]
    for name, sc, weight, direction in axis_data:
        axis_rows.append([
            Paragraph(safe_text(name), styles["table_cell"]),
            Paragraph(f"<b>{sc:.1f}</b>", styles["table_cell"]),
            Paragraph(weight, styles["table_cell"]),
            Paragraph(direction, styles["table_cell"]),
        ])
    axis_table = Table(axis_rows, colWidths=[2.3 * inch, 0.8 * inch, 1.4 * inch, 2 * inch])
    axis_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(axis_table)

    # Sub-score chart
    story.append(Spacer(1, 0.15 * inch))
    story.append(Image(str(subscore_chart), width=6.5 * inch, height=4 * inch))

    # ---- Section 3: Year-by-Year Projection ----
    story.append(Paragraph("3. Year-by-Year Projection (Base Scenario)", styles["h1"]))

    proj_rows = [[
        Paragraph("<b>Year</b>", styles["table_header"]),
        Paragraph("<b>Moat Score</b>", styles["table_header"]),
        Paragraph("<b>Cumulative Decay</b>", styles["table_header"]),
        Paragraph("<b>Interpretation</b>", styles["table_header"]),
    ]]
    for p in scores["composite"]["base_projection"]:
        year = p["year"]
        score = p["moat_score"]
        decay = p["decay_pct"]
        if year == 0:
            interp = "Initial state — full moat intact"
        elif score >= 70:
            interp = "Durable — moat remains strong"
        elif score >= 50:
            interp = "Eroding — material decay underway"
        elif score >= 30:
            interp = "At Risk — moat largely eroded"
        else:
            interp = "Terminal — moat effectively gone"
        proj_rows.append([
            Paragraph(f"Y{year}", styles["table_cell"]),
            Paragraph(f"<b>{score:.1f}</b>", styles["table_cell"]),
            Paragraph(f"{decay:.1f}%", styles["table_cell"]),
            Paragraph(interp, styles["table_cell"]),
        ])
    proj_table = Table(proj_rows, colWidths=[0.8 * inch, 1.2 * inch, 1.5 * inch, 3 * inch])
    proj_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (2, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(proj_table)

    # Narrative for milestones (if provided)
    if narrative and narrative.get("year_milestones"):
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Year-by-Year Milestones & Threat Events", styles["h2"]))
        for m in narrative["year_milestones"]:
            story.append(Paragraph(
                f"<b>Y{m.get('year', '?')}:</b> {safe_text(m.get('description', ''))}",
                styles["body"]))

    # ---- Section 4: Scenario Analysis ----
    story.append(Paragraph("4. Scenario Analysis", styles["h1"]))
    story.append(Paragraph(
        "Three scenarios stress-test the projection against AI-disruption-rate uncertainty and market/trend "
        "drift. Bull: AI disruption 40% slower, market +10, trend +5. Bear: AI disruption 50% faster, "
        "market -15, trend -10. Probability weights: 25% / 50% / 25%.",
        styles["body"]))

    sc_rows = [[
        Paragraph("<b>Scenario</b>", styles["table_header"]),
        Paragraph("<b>Probability</b>", styles["table_header"]),
        Paragraph("<b>M0</b>", styles["table_header"]),
        Paragraph("<b>Lambda</b>", styles["table_header"]),
        Paragraph("<b>Y5 Score</b>", styles["table_header"]),
    ]]
    for name in ["bull", "base", "bear"]:
        s = scores["scenarios"][name]
        sc_rows.append([
            Paragraph(name.capitalize(), styles["table_cell"]),
            Paragraph(f"{s['probability']*100:.0f}%", styles["table_cell"]),
            Paragraph(f"{s['m0']:.1f}", styles["table_cell"]),
            Paragraph(f"{s['lambda']:.4f}", styles["table_cell"]),
            Paragraph(f"<b>{s['y5_score']:.1f}</b>", styles["table_cell"]),
        ])
    sc_table = Table(sc_rows, colWidths=[1.4 * inch, 1.2 * inch, 1 * inch, 1.2 * inch, 1.2 * inch])
    sc_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sc_table)

    # ---- Section 5: AI Disruption Deep-Dive ----
    story.append(Paragraph("5. AI Disruption Deep-Dive", styles["h1"]))
    ai = scores["axes"]["ai_disruption_exposure"]
    story.append(Paragraph(
        f"AI Disruption Exposure: <b>{ai['axis_score']:.1f} / 100</b> "
        f"(higher = more exposed). This is the dominant erosion force over the 5-year horizon. "
        f"The decay constant lambda = (AI Exposure / 100) × 0.40 = {scores['composite']['lambda']:.4f}.",
        styles["body"]))

    ai_sub_rows = [[
        Paragraph("<b>Sub-Score</b>", styles["table_header"]),
        Paragraph("<b>Value</b>", styles["table_header"]),
        Paragraph("<b>Weight</b>", styles["table_header"]),
        Paragraph("<b>Direction</b>", styles["table_header"]),
    ]]
    sub_labels = [
        ("feature_automatability_pct", "% of features LLMs can replicate by Y5", "40%", "higher = worse"),
        ("proprietary_data_dependency_score", "Reliance on proprietary data (inverted)", "20%", "higher = better"),
        ("ux_commoditization_score", "UX pattern commoditization", "20%", "higher = worse"),
        ("workflow_complexity_score", "Workflow complexity (LLM-handlable)", "20%", "higher = worse"),
    ]
    for key, label, weight, direction in sub_labels:
        val = ai["sub_scores"][key]
        ai_sub_rows.append([
            Paragraph(safe_text(label), styles["table_cell"]),
            Paragraph(f"<b>{val:.1f}</b>", styles["table_cell"]),
            Paragraph(weight, styles["table_cell"]),
            Paragraph(direction, styles["table_cell"]),
        ])
    ai_table = Table(ai_sub_rows, colWidths=[2.8 * inch, 0.8 * inch, 0.8 * inch, 2.1 * inch])
    ai_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(ai_table)

    # Per-feature automatability table (if provided in narrative)
    if narrative and narrative.get("feature_automatability_table"):
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Per-Feature Automatability Analysis", styles["h2"]))
        feat_rows = [[
            Paragraph("<b>Feature</b>", styles["table_header"]),
            Paragraph("<b>Automatability (Y3)</b>", styles["table_header"]),
            Paragraph("<b>Automatability (Y5)</b>", styles["table_header"]),
            Paragraph("<b>Rationale</b>", styles["table_header"]),
        ]]
        for f in narrative["feature_automatability_table"]:
            feat_rows.append([
                Paragraph(safe_text(f.get("feature", "")), styles["table_cell"]),
                Paragraph(f"{f.get('y3', 0)}%", styles["table_cell"]),
                Paragraph(f"{f.get('y5', 0)}%", styles["table_cell"]),
                Paragraph(safe_text(f.get("rationale", "")), styles["table_cell"]),
            ])
        feat_table = Table(feat_rows, colWidths=[1.8 * inch, 1.2 * inch, 1.2 * inch, 2.3 * inch])
        feat_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(feat_table)

    # ---- Section 6: Pivot Roadmap OR Defend & Extend ----
    if "Pivot Required" in verdict or "Terminal" in verdict:
        story.append(Paragraph("6. Pivot Roadmap", styles["h1"]))
        if narrative and narrative.get("pivot_roadmap"):
            pr = narrative["pivot_roadmap"]
            story.append(Paragraph("Pivot Trigger Summary", styles["h2"]))
            story.append(Paragraph(safe_text(pr.get("trigger_summary", "")), styles["body"]))

            story.append(Paragraph("Pivot Options (Ranked)", styles["h2"]))
            for opt in pr.get("options", []):
                story.append(Paragraph(
                    f"<b>{safe_text(opt.get('pivot_name', ''))}</b> "
                    f"(archetype: {safe_text(opt.get('archetype', ''))}, "
                    f"E[Y5 moat] = {opt.get('expected_y5_moat_score', '?')}, "
                    f"P(success) = {opt.get('probability_of_success', '?')}%)",
                    styles["body_bold"]))
                story.append(Paragraph(
                    f"Target segment: {safe_text(opt.get('target_segment', 'N/A'))} "
                    f"(TAM: {safe_text(opt.get('target_segment_size', 'N/A'))})",
                    styles["body"]))
                story.append(Paragraph(
                    f"Value prop: {safe_text(opt.get('value_prop', 'N/A'))}",
                    styles["body"]))
                story.append(Paragraph(
                    f"Why AI can't follow: {safe_text(opt.get('why_ai_cant_follow', 'N/A'))}",
                    styles["body"]))
                story.append(Paragraph(
                    f"Tech migration: {safe_text(opt.get('tech_migration_path', 'N/A'))}",
                    styles["body"]))
                story.append(Paragraph(
                    f"Cost: {opt.get('migration_cost_estimate', '?')} engineer-months · "
                    f"Time to revenue: {opt.get('time_to_revenue', '?')} months · "
                    f"Expected value: {opt.get('expected_value', '?')}",
                    styles["body"]))
                story.append(Spacer(1, 0.1 * inch))

            story.append(Paragraph("Recommended Pivot — 18-Month Milestones", styles["h2"]))
            if pr.get("recommended"):
                rec = pr["recommended"]
                story.append(Paragraph(safe_text(rec.get("rationale", "")), styles["body"]))
                ms_rows = [[
                    Paragraph("<b>Quarter</b>", styles["table_header"]),
                    Paragraph("<b>Milestone</b>", styles["table_header"]),
                    Paragraph("<b>Success Criterion</b>", styles["table_header"]),
                    Paragraph("<b>Kill-Switch Trigger</b>", styles["table_header"]),
                ]]
                for m in rec.get("milestones", []):
                    ms_rows.append([
                        Paragraph(safe_text(m.get("quarter", "")), styles["table_cell"]),
                        Paragraph(safe_text(m.get("milestone", "")), styles["table_cell"]),
                        Paragraph(safe_text(m.get("success_criterion", "")), styles["table_cell"]),
                        Paragraph(safe_text(m.get("kill_switch", "")), styles["table_cell"]),
                    ])
                ms_table = Table(ms_rows, colWidths=[0.7 * inch, 1.8 * inch, 2 * inch, 2 * inch])
                ms_table.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(ms_table)

            if pr.get("sunset_plan") and "Terminal" in verdict:
                story.append(Paragraph("Sunset Plan (Terminal Verdict)", styles["h2"]))
                for line in pr["sunset_plan"]:
                    story.append(Paragraph(f"• {safe_text(line)}", styles["body"]))
        else:
            story.append(Paragraph(
                "<i>Pivot roadmap not yet generated. The LLM should populate narrative.pivot_roadmap "
                "per references/pivot-roadmap.md.</i>",
                styles["body"]))
    else:
        story.append(Paragraph("6. Defend &amp; Extend Plan", styles["h1"]))
        if narrative and narrative.get("defend_extend_plan"):
            for move in narrative["defend_extend_plan"]:
                story.append(Paragraph(
                    f"<b>{safe_text(move.get('move', ''))}</b> — "
                    f"strengthens: {safe_text(move.get('axis', ''))}, "
                    f"cost: {safe_text(move.get('cost', ''))}, "
                    f"expected lift: +{move.get('expected_lift', '?')} points, "
                    f"priority: {safe_text(move.get('priority', ''))}",
                    styles["body"]))
        else:
            story.append(Paragraph(
                "<i>Defend &amp; extend plan not yet generated. The LLM should populate "
                "narrative.defend_extend_plan per references/pivot-roadmap.md.</i>",
                styles["body"]))

    # ---- Section 7: Codebase Snapshot (if scan provided) ----
    if scan and "error" not in scan:
        story.append(Paragraph("7. Codebase Snapshot", styles["h1"]))
        snap_rows = [
            ["Primary language", scan.get("primary_language", "N/A")],
            ["Total LOC", f"{scan.get('total_loc', 0):,}"],
            ["Source files", str(scan.get("source_file_count", 0))],
            ["Test files", str(scan.get("test_file_count", 0))],
            ["Test-to-source ratio", f"{scan.get('test_to_source_ratio', 0):.2f}"],
            ["Dependencies", str(scan.get("dependency_count", 0))],
            ["Tech-debt markers", str(scan.get("tech_debt", {}).get("total_markers", 0))],
            ["Markers per 1k LOC", f"{scan.get('tech_debt_density_per_1k_loc', 0):.2f}"],
            ["Largest file (LOC)", f"{scan.get('largest_file_loc', 0):,}"],
            ["README present", "Yes" if scan.get("readme_present") else "No"],
            ["License present", "Yes" if scan.get("license_present") else "No"],
            ["CI configured", "Yes" if scan.get("ci_present") else "No"],
            ["Last commit", scan.get("last_commit_date", "N/A") or "N/A"],
        ]
        snap_table_rows = [[
            Paragraph("<b>Metric</b>", styles["table_header"]),
            Paragraph("<b>Value</b>", styles["table_header"]),
        ]]
        for k, v in snap_rows:
            snap_table_rows.append([
                Paragraph(safe_text(k), styles["table_cell"]),
                Paragraph(safe_text(v), styles["table_cell"]),
            ])
        snap_table = Table(snap_table_rows, colWidths=[2.5 * inch, 4 * inch])
        snap_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(snap_table)

        # Languages breakdown
        if scan.get("languages_pct"):
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("Language Distribution", styles["h2"]))
            lang_rows = [[
                Paragraph("<b>Language</b>", styles["table_header"]),
                Paragraph("<b>% of LOC</b>", styles["table_header"]),
            ]]
            for lang, pct in list(scan["languages_pct"].items())[:8]:
                lang_rows.append([
                    Paragraph(safe_text(lang), styles["table_cell"]),
                    Paragraph(f"{pct:.1f}%", styles["table_cell"]),
                ])
            lang_table = Table(lang_rows, colWidths=[2.5 * inch, 1.5 * inch])
            lang_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(lang_table)

    # ---- Appendix A: Evidence Index ----
    if evidence:
        story.append(Paragraph("Appendix A: Evidence Index", styles["h1"]))
        story.append(Paragraph(
            f"Total evidence entries: <b>{len(evidence)}</b>. Each sub-score in this report traces "
            f"to at least one entry below.",
            styles["body"]))
        ev_rows = [[
            Paragraph("<b>ID</b>", styles["table_header"]),
            Paragraph("<b>Metric</b>", styles["table_header"]),
            Paragraph("<b>Value</b>", styles["table_header"]),
            Paragraph("<b>Source</b>", styles["table_header"]),
            Paragraph("<b>Conf.</b>", styles["table_header"]),
        ]]
        for ev in evidence[:50]:  # cap at 50 for brevity
            ev_rows.append([
                Paragraph(safe_text(ev.get("evidence_id", "")), styles["small"]),
                Paragraph(safe_text(ev.get("metric", ""))[:80], styles["small"]),
                Paragraph(safe_text(ev.get("value", ""))[:40], styles["small"]),
                Paragraph(safe_text(ev.get("source_name", ""))[:30], styles["small"]),
                Paragraph(safe_text(ev.get("confidence", "")), styles["small"]),
            ])
        ev_table = Table(ev_rows, colWidths=[0.6 * inch, 2.5 * inch, 1.2 * inch, 1.7 * inch, 0.5 * inch])
        ev_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(ev_table)
        if len(evidence) > 50:
            story.append(Paragraph(
                f"<i>... and {len(evidence) - 50} more entries in the JSON bundle.</i>",
                styles["small_italic"]))

    # ---- Appendix B: Calculation Trace ----
    story.append(Paragraph("Appendix B: Calculation Trace", styles["h1"]))
    story.append(Paragraph(
        "Every arithmetic step the script performed, in order. Same input + same script version = identical trace.",
        styles["body"]))
    for step in scores.get("calculation_trace", []):
        story.append(Paragraph(f"<b>{step.get('step', '')}</b>: {safe_text(step.get('description', ''))}", styles["body_bold"]))
        if "values" in step:
            vals = step["values"]
            val_str = ", ".join(f"{k}={v}" for k, v in vals.items())
            story.append(Paragraph(f"   <font face='Courier' size='8'>{safe_text(val_str)}</font>", styles["small"]))

    # Overrides
    if scores.get("overrides_applied"):
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Overrides Applied", styles["h2"]))
        for ov in scores["overrides_applied"]:
            story.append(Paragraph(
                f"<b>Path:</b> <font face='Courier' size='8'>{safe_text(ov['path'])}</font>",
                styles["body"]))
            story.append(Paragraph(
                f"<b>Original:</b> {ov.get('original_value')} → <b>New:</b> {ov.get('new_value')}",
                styles["body"]))
            story.append(Paragraph(
                f"<b>Justification:</b> {safe_text(ov.get('justification', ''))}",
                styles["body"]))
            if ov.get("evidence_citations"):
                story.append(Paragraph(
                    f"<b>Evidence:</b> {', '.join(ov['evidence_citations'])}",
                    styles["small"]))

    doc.build(story)


def footer_callback(canv: canvas.Canvas, doc):
    """Footer with page number and project name."""
    canv.saveState()
    canv.setFont("Helvetica", 7)
    canv.setFillColor(colors.grey)
    page_num = canv.getPageNumber()
    if page_num > 1:
        canv.drawString(0.75 * inch, 0.5 * inch, f"5-Year Forecast · page {page_num}")
        canv.drawRightString(7.75 * inch, 0.5 * inch, "codebase-5yr-forecast skill v1.0")
    canv.restoreState()


def _dominant_risk_axis(scores: dict) -> str:
    """Identify which axis contributed most negatively to the score."""
    axes = scores["axes"]
    # AI exposure is dominant risk if > 50 (it's inverted in composite)
    ai = axes["ai_disruption_exposure"]["axis_score"]
    tech = axes["technical_moat"]["axis_score"]
    trend = axes["trend_alignment"]["axis_score"]
    market = axes["market_demand"]["axis_score"]

    # Find the lowest non-AI axis, and check AI separately
    candidates = [
        (f"AI Disruption Exposure (score {ai:.1f}/100 — high exposure)", 100 - ai),  # invert for "how bad"
        (f"Technical Moat weakness (score {tech:.1f}/100)", 100 - tech),
        (f"Trend Alignment against project (score {trend:.1f}/100)", 100 - trend),
        (f"Market Demand weakness (score {market:.1f}/100)", 100 - market),
    ]
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


# ---------------------------------------------------------------------------
# JSON bundle
# ---------------------------------------------------------------------------

def build_json_bundle(
    scores: dict,
    scan: dict | None,
    evidence: list | None,
    scoring_input: dict | None,
    narrative: dict | None,
) -> dict:
    """Build the machine-readable JSON bundle."""
    bundle = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_name": scores.get("project_name"),
        "skill_version": "1.0.0",
        "script_version": scores.get("script_version", "1.0.0"),
        "scoring_methodology_version": scores.get("scoring_methodology_version", "1.0.0"),
        "input_hash": scores.get("input_hash"),
        "verdict": scores.get("verdict"),
        "expected_y5": scores.get("expected_y5"),
        "expected_m0": scores.get("expected_m0"),
        "composite": scores.get("composite"),
        "axes": scores.get("axes"),
        "scenarios": scores.get("scenarios"),
        "confidence_interval": scores.get("confidence_interval"),
        "overrides_applied": scores.get("overrides_applied", []),
        "calculation_trace": scores.get("calculation_trace", []),
        "scoring_input": scoring_input,
        "scan": scan,
        "evidence": evidence or [],
        "narrative": narrative or {},
        "evidence_freshness": _evidence_freshness(evidence),
        "manifest": {
            "skill_version": "1.0.0",
            "script_version": scores.get("script_version", "1.0.0"),
            "scoring_methodology_version": scores.get("scoring_methodology_version", "1.0.0"),
            "input_hash": scores.get("input_hash"),
            "evidence_count": len(evidence) if evidence else 0,
            "evidence_freshness": _evidence_freshness(evidence),
            "overrides_applied": len(scores.get("overrides_applied", [])),
            "computed_at": scores.get("computed_at"),
            "model_used": os.environ.get("FORECAST_MODEL", "unknown"),
            "tool_used": os.environ.get("FORECAST_TOOL", "unknown"),
        },
    }
    # Compute output hash
    canonical = json.dumps({k: v for k, v in bundle.items() if k != "generated_at"},
                          sort_keys=True, separators=(",", ":"), default=str)
    bundle["manifest"]["output_hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return bundle


def _evidence_freshness(evidence: list | None) -> str:
    if not evidence:
        return "none"
    now = datetime.now(timezone.utc)
    max_age_days = 0
    for ev in evidence:
        retrieved = ev.get("retrieved_at")
        if not retrieved:
            continue
        try:
            dt = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
            age = (now - dt).days
            if age > max_age_days:
                max_age_days = age
        except (ValueError, TypeError):
            continue
    if max_age_days <= 1:
        return "fresh"
    if max_age_days <= 7:
        return "recent"
    return "stale"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate 5-year forecast PDF + JSON bundle")
    parser.add_argument("--scores", required=True, help="scores.json from moat_calculator.py")
    parser.add_argument("--scan", help="scan.json from codebase_scanner.py (optional)")
    parser.add_argument("--evidence", help="evidence.json (array of evidence entries)")
    parser.add_argument("--scoring-input", help="scoring_input.json used by the calculator")
    parser.add_argument("--narrative", help="narrative.json (LLM-written prose sections)")
    parser.add_argument("--output-dir", default="/home/z/my-project/download/",
                        help="Output directory")
    parser.add_argument("--project-name", help="Override project name (default: from scores)")
    parser.add_argument("--version", action="version", version=f"generate_report.py v{SCRIPT_VERSION}")
    args = parser.parse_args()

    setup_fonts()

    # Load inputs
    with open(args.scores, "r", encoding="utf-8") as f:
        scores = json.load(f)

    scan = None
    if args.scan:
        with open(args.scan, "r", encoding="utf-8") as f:
            scan = json.load(f)

    evidence = None
    if args.evidence:
        with open(args.evidence, "r", encoding="utf-8") as f:
            evidence = json.load(f)

    scoring_input = None
    if args.scoring_input:
        with open(args.scoring_input, "r", encoding="utf-8") as f:
            scoring_input = json.load(f)

    narrative = None
    if args.narrative:
        with open(args.narrative, "r", encoding="utf-8") as f:
            narrative = json.load(f)

    if args.project_name:
        scores["project_name"] = args.project_name

    project_slug = slugify(scores.get("project_name", "project"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_dir = output_dir / "forecast_charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = output_dir / f"{project_slug}_5yr_forecast.pdf"
    json_path = output_dir / f"{project_slug}_5yr_forecast.json"

    # Build PDF
    build_pdf(scores, scan, evidence, scoring_input, narrative, pdf_path, chart_dir)
    print(f"Wrote PDF: {pdf_path}", file=sys.stderr)

    # Build JSON bundle
    bundle = build_json_bundle(scores, scan, evidence, scoring_input, narrative)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote JSON: {json_path}", file=sys.stderr)

    print(f"\nVerdict: {scores['verdict']}", file=sys.stderr)
    print(f"Expected Y5: {scores['expected_y5']:.1f} / 100", file=sys.stderr)


if __name__ == "__main__":
    main()
