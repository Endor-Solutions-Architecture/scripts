#!/usr/bin/env python3
"""
Generate a PDF analytics report from an Endor Labs analytics JSON export.

Produces a branded, dashboard-style PDF with:
  - Endor Labs logo and report header
  - Report metadata (filters, date range, created by)
  - Vulnerabilities Snapshot (summary cards)
  - Severity Distribution (donut chart)
  - Vulnerabilities Over Time (line chart)
  - Severity Breakdown (stacked area chart)
  - Time for Vulnerabilities Issues Resolved (line chart)
  - Detailed data table
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# ---------------------------------------------------------------------------
# Endor Labs brand palette
# ---------------------------------------------------------------------------
BRAND = {
    # Primary
    "green": "#00D26A",
    "dark": "#1A1A2E",
    "dark_secondary": "#2D2D44",
    # Severity (matches Endor dashboard warm palette)
    "critical": "#7B2D26",
    "high": "#C4532D",
    "medium": "#E8963F",
    "low": "#F0C75E",
    # Chart lines
    "newly_discovered": "#C4532D",
    "resolved": "#00D26A",
    "avg_line": "#3D6B8E",
    "min_line": "#5A9A7A",
    "max_line": "#C4532D",
    # UI
    "card_bg": "#F8F9FA",
    "card_border": "#E8ECF0",
    "text_primary": "#1A1A2E",
    "text_secondary": "#5A6577",
    "text_muted": "#8E99A8",
    "white": "#FFFFFF",
    "table_header_bg": "#1A1A2E",
    "table_header_text": "#FFFFFF",
    "table_row_alt": "#F8F9FA",
    "table_border": "#DEE2E6",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a PDF report from an Endor Labs analytics JSON export."
    )
    parser.add_argument(
        "-f", "--file", required=True,
        help="Path to the analytics JSON file exported from Endor Labs.",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output PDF path. Defaults to generated_reports/<timestamp>.pdf",
    )
    return parser.parse_args()


def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def _parse_dates(entries: list[dict]) -> list[datetime]:
    return [datetime.fromisoformat(e["date"].replace("Z", "+00:00")) for e in entries]


def _format_number(n) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _extract_date_range_hours(filter_str: str) -> int | None:
    """Extract the hour range from a filter like 'now(-2160h)'."""
    match = re.search(r"now\(-(\d+)h\)", filter_str)
    if match:
        return int(match.group(1))
    return None


def _extract_severity_levels(filter_str: str) -> list[str]:
    """Extract severity levels from filter string."""
    levels = re.findall(r"FINDING_LEVEL_(\w+)", filter_str)
    return [l.title() for l in levels]


def _extract_finding_tags(filter_str: str) -> list[str]:
    """Extract human-readable finding tags from filter."""
    tags = re.findall(r"FINDING_TAGS_(\w+)", filter_str)
    mapping = {
        "REACHABLE_FUNCTION": "Reachable Function",
        "REACHABLE_DEPENDENCY": "Reachable Dependency",
        "NORMAL": "Normal",
    }
    return [mapping.get(t, t.replace("_", " ").title()) for t in tags]


def _compute_severity_totals(over_time: dict) -> dict:
    """Sum up all severity counts from newly_discovered entries."""
    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for entry in over_time.get("newly_discovered", []):
        for sev in totals:
            totals[sev] += entry.get(sev, 0)
    return totals


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

def _fig_to_image(fig, width: float, height: float) -> Image:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)


def _configure_date_axis(ax, dates: list[datetime]):
    if not dates:
        return
    all_dates = sorted(dates)
    date_range = (all_dates[-1] - all_dates[0]).days
    padding = timedelta(days=max(date_range * 0.05, 2))
    ax.set_xlim(all_dates[0] - padding, all_dates[-1] + padding)

    if date_range <= 30:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    elif date_range <= 180:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())

    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)


def _style_chart(ax, fig):
    fig.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(colors=BRAND["text_secondary"], labelsize=8)


def build_snapshot_image(snapshot: dict, page_width: float) -> Image:
    """Render the summary cards with colored accent bars."""
    labels = [
        "Newly\nDiscovered",
        "Resolved",
        "Mean Time to\nResolve (days)",
        "Min Time to\nResolve (days)",
        "Max Time to\nResolve (days)",
    ]
    keys = [
        "newly_discovered",
        "resolved",
        "average_time_to_resolve",
        "minimum_time_to_resolve",
        "maximum_time_to_resolve",
    ]
    values = [snapshot.get(k, 0) for k in keys]

    n = len(labels)
    fig, axes = plt.subplots(1, n, figsize=(page_width / 72, 1.5))
    fig.set_facecolor(BRAND["white"])
    fig.subplots_adjust(wspace=0.35)

    for ax, label, val in zip(axes, labels, values):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Card background
        card = FancyBboxPatch(
            (0.03, 0.05), 0.94, 0.90,
            boxstyle="round,pad=0.04",
            facecolor=BRAND["card_bg"],
            edgecolor=BRAND["card_border"],
            linewidth=0.8,
        )
        ax.add_patch(card)

        # Consistent green accent bar at top of card
        bar = FancyBboxPatch(
            (0.03, 0.87), 0.94, 0.08,
            boxstyle="round,pad=0.02",
            facecolor=BRAND["green"],
            edgecolor="none",
        )
        ax.add_patch(bar)

        ax.text(0.5, 0.65, label, ha="center", va="center",
                fontsize=7, color=BRAND["text_secondary"], fontweight="medium")
        ax.text(0.5, 0.30, _format_number(val), ha="center", va="center",
                fontsize=16, color=BRAND["text_primary"], fontweight="bold")

    return _fig_to_image(fig, page_width, 1.5 * 72)


def build_severity_donut(over_time: dict, page_width: float) -> Image | None:
    """Donut chart showing total severity distribution."""
    totals = _compute_severity_totals(over_time)
    if sum(totals.values()) == 0:
        return None

    fig, ax = plt.subplots(figsize=(page_width / 72, 2.6))
    fig.set_facecolor(BRAND["white"])

    labels_order = ["critical", "high", "medium", "low"]
    display_labels = ["Critical", "High", "Medium", "Low"]
    colors = [BRAND[s] for s in labels_order]
    sizes = [totals[s] for s in labels_order]

    # Filter out zero values
    filtered = [(l, s, c) for l, s, c in zip(display_labels, sizes, colors) if s > 0]
    if not filtered:
        plt.close(fig)
        return None

    f_labels, f_sizes, f_colors = zip(*filtered)

    wedges, texts, autotexts = ax.pie(
        f_sizes, labels=None, colors=f_colors, autopct="%1.0f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops=dict(width=0.4, edgecolor=BRAND["white"], linewidth=2),
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")
        t.set_color(BRAND["white"])

    # Center total count
    total = sum(f_sizes)
    ax.text(0, 0.06, _format_number(total), ha="center", va="center",
            fontsize=22, fontweight="bold", color=BRAND["text_primary"])
    ax.text(0, -0.10, "Total", ha="center", va="center",
            fontsize=9, color=BRAND["text_secondary"])

    # Legend
    legend = ax.legend(
        wedges, [f"{l}  ({_format_number(s)})" for l, s in zip(f_labels, f_sizes)],
        loc="center left", bbox_to_anchor=(0.85, 0.5),
        fontsize=9, frameon=False,
    )
    for text in legend.get_texts():
        text.set_color(BRAND["text_primary"])

    ax.set_aspect("equal")
    fig.tight_layout()

    return _fig_to_image(fig, page_width, 2.6 * 72)


def build_vulns_over_time_chart(over_time: dict, page_width: float) -> Image:
    fig, ax = plt.subplots(figsize=(page_width / 72, 2.4))
    all_dates = []
    nd = over_time.get("newly_discovered", [])
    res = over_time.get("resolved", [])

    if nd:
        dates = _parse_dates(nd)
        all_dates.extend(dates)
        totals = [e["critical"] + e["high"] + e["medium"] + e["low"] for e in nd]
        ax.fill_between(dates, totals, alpha=0.1, color=BRAND["newly_discovered"])
        ax.plot(dates, totals, color=BRAND["newly_discovered"], marker="o",
                markersize=5, linewidth=2, label="Newly Discovered",
                markerfacecolor=BRAND["white"], markeredgewidth=1.5,
                markeredgecolor=BRAND["newly_discovered"])

    if res:
        dates_r = _parse_dates(res)
        all_dates.extend(dates_r)
        totals_r = [e["critical"] + e["high"] + e["medium"] + e["low"] for e in res]
        ax.fill_between(dates_r, totals_r, alpha=0.1, color=BRAND["resolved"])
        ax.plot(dates_r, totals_r, color=BRAND["resolved"], marker="o",
                markersize=5, linewidth=2, label="Resolved",
                markerfacecolor=BRAND["white"], markeredgewidth=1.5,
                markeredgecolor=BRAND["resolved"])

    ax.set_ylabel("Count", fontsize=9, color=BRAND["text_secondary"])
    ax.legend(fontsize=8, loc="upper right", framealpha=0.95,
              edgecolor=BRAND["card_border"], fancybox=True)
    _configure_date_axis(ax, all_dates)
    _style_chart(ax, fig)
    fig.tight_layout()

    return _fig_to_image(fig, page_width, 2.4 * 72)


def build_severity_breakdown_chart(over_time: dict, page_width: float) -> Image | None:
    nd = over_time.get("newly_discovered", [])
    if not nd or len(nd) < 2:
        return None

    fig, ax = plt.subplots(figsize=(page_width / 72, 2.4))
    dates = _parse_dates(nd)

    critical = [e["critical"] for e in nd]
    high = [e["high"] for e in nd]
    medium = [e["medium"] for e in nd]
    low = [e["low"] for e in nd]

    ax.stackplot(
        dates, critical, high, medium, low,
        labels=["Critical", "High", "Medium", "Low"],
        colors=[BRAND["critical"], BRAND["high"], BRAND["medium"], BRAND["low"]],
        alpha=0.85,
    )

    ax.set_ylabel("Count", fontsize=9, color=BRAND["text_secondary"])
    ax.legend(fontsize=8, loc="upper right", framealpha=0.95,
              edgecolor=BRAND["card_border"], fancybox=True)
    _configure_date_axis(ax, dates)
    _style_chart(ax, fig)
    fig.tight_layout()

    return _fig_to_image(fig, page_width, 2.4 * 72)


def build_time_to_resolve_chart(time_data: list[dict], page_width: float) -> Image:
    fig, ax = plt.subplots(figsize=(page_width / 72, 2.4))

    if time_data:
        dates = _parse_dates(time_data)
        avgs = [e.get("avg", 0) for e in time_data]
        mins = [e.get("min", 0) for e in time_data]
        maxs = [e.get("max", 0) for e in time_data]

        if len(dates) > 1:
            ax.fill_between(dates, mins, maxs, alpha=0.1, color=BRAND["avg_line"])

        ax.plot(dates, avgs, color=BRAND["avg_line"], marker="o",
                markersize=5, linewidth=2, label="Average",
                markerfacecolor=BRAND["white"], markeredgewidth=1.5,
                markeredgecolor=BRAND["avg_line"])
        ax.plot(dates, mins, color=BRAND["min_line"], marker="s",
                markersize=4, linewidth=1.2, linestyle="--", label="Min")
        ax.plot(dates, maxs, color=BRAND["max_line"], marker="s",
                markersize=4, linewidth=1.2, linestyle="--", label="Max")

        _configure_date_axis(ax, dates)

    ax.set_ylabel("Days", fontsize=9, color=BRAND["text_secondary"])
    ax.legend(fontsize=8, loc="upper right", framealpha=0.95,
              edgecolor=BRAND["card_border"], fancybox=True)
    _style_chart(ax, fig)
    fig.tight_layout()

    return _fig_to_image(fig, page_width, 2.4 * 72)


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

def _add_page_footer(canvas, doc):
    """Draw page number and thin accent bar at bottom of each page."""
    canvas.saveState()
    page_w, page_h = doc.pagesize

    # Bottom accent line
    canvas.setStrokeColor(HexColor(BRAND["green"]))
    canvas.setLineWidth(1.5)
    canvas.line(inch, 0.5 * inch, page_w - inch, 0.5 * inch)

    # Page number
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor(BRAND["text_muted"]))
    canvas.drawRightString(
        page_w - inch, 0.35 * inch,
        f"Page {doc.page}"
    )
    canvas.drawString(inch, 0.35 * inch, "Endor Labs Analytics Report")
    canvas.restoreState()


def build_pdf(data: dict, output_path: str):
    page = landscape(letter)
    page_w = page[0] - 2 * inch

    doc = SimpleDocTemplate(
        output_path,
        pagesize=page,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=20, textColor=HexColor(BRAND["dark"]),
        spaceAfter=2, fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=9, textColor=HexColor(BRAND["text_secondary"]),
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"],
        fontSize=13, textColor=HexColor(BRAND["dark"]),
        spaceBefore=14, spaceAfter=6,
        fontName="Helvetica-Bold",
        borderColor=HexColor(BRAND["green"]),
        borderWidth=0,
        borderPadding=0,
        leftIndent=0,
    )
    meta_label_style = ParagraphStyle(
        "MetaLabel", parent=styles["Normal"],
        fontSize=8, textColor=HexColor(BRAND["text_muted"]),
    )
    meta_value_style = ParagraphStyle(
        "MetaValue", parent=styles["Normal"],
        fontSize=9, textColor=HexColor(BRAND["text_primary"]),
    )

    elements = []

    # ---- Header: title ----
    meta = data.get("report_metadata", {})
    created = meta.get("created_at", "")
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created_str = dt.strftime("%B %d, %Y at %H:%M UTC")
        except ValueError:
            created_str = created
    else:
        created_str = "N/A"

    header_items = [
        [
            Paragraph("EndorLabs - Analytics Report", title_style),
            Paragraph(f"Generated: {created_str}", subtitle_style),
        ]
    ]

    header_table = Table(
        header_items,
        colWidths=[page_w * 0.6, page_w * 0.4],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)

    # Green accent divider
    divider_table = Table([[""]],
        colWidths=[page_w],
        rowHeights=[3],
    )
    divider_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["green"])),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(Spacer(1, 6))
    elements.append(divider_table)
    elements.append(Spacer(1, 10))

    # ---- Metadata section ----
    project_filter = meta.get("project_filter", "")
    finding_filter = meta.get("finding_filter", "")
    created_by = meta.get("created_by", "")

    hours = _extract_date_range_hours(finding_filter)
    date_range_str = f"{hours // 24} days" if hours else "N/A"
    severities = _extract_severity_levels(finding_filter)
    severity_str = ", ".join(severities) if severities else "All"
    tags = _extract_finding_tags(finding_filter)
    tags_str = ", ".join(tags) if tags else "N/A"
    user_str = created_by.split("@")[0] + "@" + created_by.split("@")[1] if "@" in created_by else created_by

    meta_data = [
        ["Date Range", date_range_str, "Severity Levels", severity_str],
        ["Project Filter", project_filter or "None", "Finding Tags", tags_str],
        ["Created By", user_str, "", ""],
    ]

    meta_table_data = []
    for row in meta_data:
        table_row = []
        for i in range(0, len(row), 2):
            label = row[i]
            value = row[i + 1]
            if label:
                table_row.append(Paragraph(f"<b>{label}</b>", meta_label_style))
                table_row.append(Paragraph(value, meta_value_style))
            else:
                table_row.extend(["", ""])
        meta_table_data.append(table_row)

    meta_table = Table(
        meta_table_data,
        colWidths=[page_w * 0.12, page_w * 0.38, page_w * 0.12, page_w * 0.38],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["card_bg"])),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["card_border"])),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # ---- Section helper ----
    def section_header(title: str) -> Paragraph:
        return Paragraph(
            f'<font color="{BRAND["green"]}">|</font>&nbsp;&nbsp;{title}',
            section_style,
        )

    # ---- Snapshot cards ----
    snapshot = data.get("vulnerabilities_snapshot", {})
    if snapshot:
        elements.append(KeepTogether([
            section_header("Vulnerabilities Snapshot"),
            build_snapshot_image(snapshot, page_w),
            Spacer(1, 6),
        ]))

    # ---- Severity donut + Vulns over time side by side ----
    over_time = data.get("vulnerabilities_over_time", {})
    donut_img = build_severity_donut(over_time, page_w * 0.38)
    has_over_time = over_time.get("newly_discovered") or over_time.get("resolved")

    if donut_img and has_over_time:
        vot_img = build_vulns_over_time_chart(over_time, page_w * 0.58)
        side_table = Table(
            [[donut_img, vot_img]],
            colWidths=[page_w * 0.40, page_w * 0.60],
        )
        side_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(KeepTogether([
            section_header("Severity Distribution & Trends"),
            side_table,
            Spacer(1, 6),
        ]))
    elif has_over_time:
        elements.append(KeepTogether([
            section_header("Vulnerabilities Over Time"),
            build_vulns_over_time_chart(over_time, page_w),
            Spacer(1, 6),
        ]))

    # ---- Severity breakdown (stacked area) ----
    severity_img = build_severity_breakdown_chart(over_time, page_w)
    if severity_img:
        elements.append(KeepTogether([
            section_header("Severity Breakdown Over Time"),
            severity_img,
            Spacer(1, 6),
        ]))

    # ---- Time to resolve ----
    time_data = data.get("time_for_issues_resolved", [])
    if time_data:
        elements.append(KeepTogether([
            section_header("Time to Resolve"),
            build_time_to_resolve_chart(time_data, page_w),
            Spacer(1, 6),
        ]))

    # ---- Detailed data table ----
    nd_entries = over_time.get("newly_discovered", [])
    res_entries = over_time.get("resolved", [])
    if nd_entries or res_entries:
        elements.append(section_header("Detailed Vulnerability Data"))

        # Build table: Date | New Critical | New High | New Med | New Low | New Total | Resolved Total
        table_data = [
            [
                Paragraph("<b>Date</b>", meta_label_style),
                Paragraph("<b>New Critical</b>", meta_label_style),
                Paragraph("<b>New High</b>", meta_label_style),
                Paragraph("<b>New Medium</b>", meta_label_style),
                Paragraph("<b>New Low</b>", meta_label_style),
                Paragraph("<b>New Total</b>", meta_label_style),
                Paragraph("<b>Resolved</b>", meta_label_style),
            ]
        ]

        # Merge all dates
        all_entries = {}
        for entry in nd_entries:
            d = entry["date"][:10]
            all_entries.setdefault(d, {"nd": None, "res": None})
            all_entries[d]["nd"] = entry
        for entry in res_entries:
            d = entry["date"][:10]
            all_entries.setdefault(d, {"nd": None, "res": None})
            all_entries[d]["res"] = entry

        cell_style = ParagraphStyle("Cell", parent=styles["Normal"],
                                     fontSize=8, textColor=HexColor(BRAND["text_primary"]))
        cell_style_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold")

        for date_str in sorted(all_entries.keys()):
            info = all_entries[date_str]
            nd_e = info["nd"]
            res_e = info["res"]
            dt_display = datetime.fromisoformat(date_str).strftime("%b %d, %Y")

            c = nd_e["critical"] if nd_e else 0
            h = nd_e["high"] if nd_e else 0
            m = nd_e["medium"] if nd_e else 0
            l = nd_e["low"] if nd_e else 0
            nd_total = c + h + m + l
            res_total = (res_e["critical"] + res_e["high"] + res_e["medium"] + res_e["low"]) if res_e else 0

            table_data.append([
                Paragraph(dt_display, cell_style),
                Paragraph(str(c), cell_style),
                Paragraph(str(h), cell_style),
                Paragraph(str(m), cell_style),
                Paragraph(str(l), cell_style),
                Paragraph(str(nd_total), cell_style_bold),
                Paragraph(str(res_total), cell_style_bold),
            ])

        col_w = page_w / 7
        detail_table = Table(
            table_data,
            colWidths=[col_w * 1.4, col_w * 0.9, col_w * 0.9,
                       col_w * 0.9, col_w * 0.9, col_w * 0.9, col_w * 0.9],
            repeatRows=1,
        )

        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]
        # Alternate row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                t_style.append(
                    ("BACKGROUND", (0, i), (-1, i), HexColor(BRAND["table_row_alt"]))
                )

        detail_table.setStyle(TableStyle(t_style))
        elements.append(detail_table)

    doc.build(elements, onFirstPage=_add_page_footer, onLaterPages=_add_page_footer)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if not os.path.isfile(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.file)

    if args.output:
        output_path = args.output
    else:
        os.makedirs("generated_reports", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"generated_reports/analytics_report_{ts}.pdf"

    build_pdf(data, output_path)
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
