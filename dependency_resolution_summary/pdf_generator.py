"""PDF generator for the dependency resolution & reachability summary.

Ported from ewok-util/pysrc/ewok_cli/utils/pdf_generator.py with two changes:
- expects row dicts from main.process_project (snake_case keys)
- looks for the logo only at endor-logo.svg next to this file
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    import cairosvg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False


class EndorPDFGenerator:
    def __init__(self, filename: str, title: str, namespace: str):
        self.filename = filename
        self.title = title
        self.namespace = namespace
        self.doc = SimpleDocTemplate(
            filename, pagesize=A4,
            rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72,
        )
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.story = []

    def _setup_styles(self):
        s = self.styles
        s.add(ParagraphStyle(name="EndorTitle", parent=s["Title"], fontSize=24,
                             spaceAfter=30, alignment=TA_CENTER,
                             textColor=colors.HexColor("#1F2937")))
        s.add(ParagraphStyle(name="EndorSubtitle", parent=s["Heading2"], fontSize=16,
                             spaceAfter=20, alignment=TA_CENTER,
                             textColor=colors.HexColor("#1F2937")))
        s.add(ParagraphStyle(name="EndorSection", parent=s["Heading2"], fontSize=14,
                             spaceAfter=12, spaceBefore=20,
                             textColor=colors.HexColor("#1F2937")))
        s.add(ParagraphStyle(name="EndorTableHeader", parent=s["Normal"], fontSize=10,
                             alignment=TA_CENTER, textColor=colors.white,
                             fontName="Helvetica-Bold"))
        s.add(ParagraphStyle(name="TableText", parent=s["Normal"], fontSize=9,
                             alignment=TA_CENTER, textColor=colors.black,
                             wordWrap="LTR"))

    def _add_logo(self) -> bool:
        path = os.path.join(os.path.dirname(__file__), "endor-logo.svg")
        if not os.path.exists(path):
            return False
        if not SVG_SUPPORT:
            print("cairosvg not available; falling back to text title")
            return False
        try:
            png = cairosvg.svg2png(url=path, output_width=800, output_height=400)
        except Exception as exc:  # libcairo missing at runtime, etc.
            print(f"Logo render failed: {exc}; falling back to text title")
            return False
        img = Image(BytesIO(png), width=4 * inch, height=2 * inch)
        img.hAlign = "CENTER"
        self.story.append(img)
        self.story.append(Spacer(1, 0.2 * inch))
        return True

    def add_title_page(self):
        if not self._add_logo():
            self.story.append(Paragraph("Endor Labs", self.styles["EndorTitle"]))
            self.story.append(Spacer(1, 0.2 * inch))
        self.story.append(Paragraph(self.title, self.styles["EndorSubtitle"]))
        self.story.append(Spacer(1, 0.3 * inch))
        for line in [
            f"<b>Namespace:</b> {self.namespace}",
            f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            "<b>Report Type:</b> Dependency Resolution & Reachability Analysis",
        ]:
            self.story.append(Paragraph(line, self.styles["Normal"]))
            self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(PageBreak())

    def add_summary_section(self, stats: dict):
        self.story.append(Paragraph("Executive Summary", self.styles["EndorSection"]))
        data = [
            ["Metric", "Value", "Percentage"],
            ["Total Projects", str(stats["total_projects"]), "100%"],
            ["Projects with Full Success", str(stats["full_success_count"]),
             f"{stats['full_success_percentage']:.1f}%"],
            ["Projects with Dependency Issues", str(stats["dependency_issues_count"]),
             f"{stats['dependency_issues_percentage']:.1f}%"],
            ["Projects with Reachability Issues", str(stats["reachability_issues_count"]),
             f"{stats['reachability_issues_percentage']:.1f}%"],
            ["", "", ""],
            ["Total Packages", str(stats["total_packages"]), "100%"],
            ["Dependency Resolution Success", str(stats["dependency_resolution_success"]),
             f"{stats['dependency_resolution_percentage']:.1f}%"],
            ["Reachability Success", str(stats["reachability_success"]),
             f"{stats['reachability_percentage']:.1f}%"],
        ]
        t = Table(data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.3 * inch))

    def _bar(self, label: str, percentage: float, color_hex: str):
        data = [[label, f"{percentage:.1f}%"], ["", ""]]
        t = Table(data, colWidths=[2 * inch, 4 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (1, 1), (1, 1), colors.HexColor(color_hex)),
            ("GRID", (0, 0), (-1, -1), 0, colors.white),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.1 * inch))

    def add_progress_bars(self, stats: dict):
        self.story.append(Paragraph("Progress Overview", self.styles["EndorSection"]))
        self._bar("Dependency Resolution Success", stats["dependency_resolution_percentage"], "#059669")
        self._bar("Reachability Analysis Success", stats["reachability_percentage"], "#06B6D4")
        self.story.append(Spacer(1, 0.2 * inch))

    def add_reachability_strategy_overview(self, stats: dict):
        self.story.append(Paragraph("Reachability Success Strategy Overview",
                                    self.styles["EndorSection"]))
        self._bar("FULL Strategy", stats.get("full_strategy_percentage", 0), "#047857")
        self._bar("PRE-COMPUTED Strategy", stats.get("precomputed_strategy_percentage", 0), "#2DD4BF")
        self.story.append(Spacer(1, 0.2 * inch))
        note = (
            "<b>Reachability Strategy Definitions:</b><br/>"
            "• <b>FULL:</b> Complete call graph analysis without fallback<br/>"
            "• <b>PRE-COMPUTED:</b> Used precomputed reachability as fallback when "
            "call graph analysis failed"
        )
        self.story.append(Paragraph(note, ParagraphStyle(
            name="ReachabilityNote", parent=self.styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#374151"),
            leftIndent=0.2 * inch, rightIndent=0.2 * inch,
            spaceAfter=12, spaceBefore=6,
        )))

    def add_project_table(self, title: str, rows: list, columns: list[str]):
        self.story.append(PageBreak())
        self.story.append(Paragraph(title, self.styles["EndorSection"]))
        if not rows:
            self.story.append(Paragraph("No projects in this category.",
                                        self.styles["Normal"]))
            return

        header_map = {
            "Project URL": "Project<br/>URL",
            "Failed Packages": "Failed<br/>Packages",
            "Reachability Failed": "Reachability<br/>Failed",
            "Reachability Strategy": "Reachability<br/>Strategy",
            "Resolution Success %": "Resolution<br/>Success %",
            "Reachability Success %": "Reachability<br/>Success %",
            "Total Failed": "Total<br/>Failed",
            "Success %": "Success<br/>%",
        }
        headers = [Paragraph(header_map.get(c, c), self.styles["EndorTableHeader"])
                   for c in columns]

        body: list = [headers]
        for row in rows:
            body.append([self._cell(row, c) for c in columns])

        n = len(columns)
        if n == 4:
            widths = [3.0 * inch, 1 * inch, 1.2 * inch, 1.3 * inch]
        elif n == 5:
            widths = [3.0 * inch, 1 * inch, 1 * inch, 1 * inch, 1.5 * inch]
        elif n == 6:
            widths = [2.5 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.2 * inch, 0.8 * inch]
        else:
            widths = [3.5 * inch] + [1 * inch] * (n - 1)

        t = Table(body, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (1, 0), (3, -1), "CENTER"),
            ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.story.append(t)
        self.story.append(Spacer(1, 0.3 * inch))

    def _cell(self, row: dict, col: str) -> Any:
        if col == "Project Name":
            name = row.get("project_name", "")
            return Paragraph(name, self.styles["TableText"]) if len(name) > 50 else name
        if col == "Total Packages":
            return str(row.get("total_packages", 0))
        if col == "Failed Packages":
            return str(row.get("dependency_resolution_failed", 0))
        if col in ("Reachability Failed", "Total Failed"):
            return str(row.get("reachability_failed", 0))
        if col == "Resolution Success %":
            total = row.get("total_packages", 0)
            failed = row.get("dependency_resolution_failed", 0)
            return f"{((total - failed) / total * 100) if total > 0 else 0:.1f}%"
        if col in ("Reachability Success %", "Success %"):
            total = row.get("total_packages", 0)
            failed = row.get("reachability_failed", 0)
            return f"{((total - failed) / total * 100) if total > 0 else 0:.1f}%"
        if col == "Reachability Strategy":
            return Paragraph(row.get("reachability_strategy", ""), self.styles["TableText"])
        if col == "Project URL":
            url = row.get("project_url", "")
            return Paragraph(f'<link href="{url}" color="blue"><u>View</u></link>',
                             self.styles["TableText"])
        return str(row.get(col, ""))

    def build(self):
        self.doc.build(self.story)


def generate_dependency_resolution_summary_pdf(
    filename: str, namespace: str, rows: list[dict]
) -> None:
    """Render the full PDF from processed project rows."""
    full_success = [r for r in rows if r["category"] == "full_success"]
    dep_issues = [r for r in rows if r["category"] == "dependency_resolution_issues"]
    reach_issues = [r for r in rows if r["category"] == "reachability_issues_only"]

    total_projects = len(rows)
    total_packages = sum(r["total_packages"] for r in rows)
    dep_success = sum(r["dependency_resolution_success"] for r in rows)
    reach_success = sum(r["reachability_success"] for r in rows)

    full_n = len([r for r in full_success if r["reachability_strategy"] == "FULL"])
    pre_n = len([r for r in full_success if r["reachability_strategy"] == "PRE-COMPUTED"])
    strategy_total = full_n + pre_n

    stats = {
        "total_projects": total_projects,
        "total_packages": total_packages,
        "dependency_resolution_success": dep_success,
        "reachability_success": reach_success,
        "dependency_resolution_percentage":
            (dep_success / total_packages * 100) if total_packages else 0,
        "reachability_percentage":
            (reach_success / total_packages * 100) if total_packages else 0,
        "full_success_count": len(full_success),
        "full_success_percentage":
            (len(full_success) / total_projects * 100) if total_projects else 0,
        "dependency_issues_count": len(dep_issues),
        "dependency_issues_percentage":
            (len(dep_issues) / total_projects * 100) if total_projects else 0,
        "reachability_issues_count": len(reach_issues),
        "reachability_issues_percentage":
            (len(reach_issues) / total_projects * 100) if total_projects else 0,
        "full_strategy_percentage": (full_n / strategy_total * 100) if strategy_total else 0,
        "precomputed_strategy_percentage":
            (pre_n / strategy_total * 100) if strategy_total else 0,
    }

    g = EndorPDFGenerator(filename, "Dependency Resolution & Reachability Report", namespace)
    g.add_title_page()
    g.add_summary_section(stats)
    g.add_progress_bars(stats)
    g.add_reachability_strategy_overview(stats)
    g.add_project_table(
        "Successfully Onboarded Projects (100% Dependency Resolution & Reachability)",
        full_success,
        ["Project Name", "Total Packages", "Reachability Strategy", "Project URL"],
    )
    g.add_project_table(
        "Projects with Dependency Resolution Issues",
        dep_issues,
        ["Project Name", "Total Packages", "Failed Packages",
         "Resolution Success %", "Project URL"],
    )
    g.add_project_table(
        "Projects with Reachability Issues Only (Dependency Resolution Success)",
        reach_issues,
        ["Project Name", "Total Packages", "Total Failed", "Success %",
         "Reachability Strategy", "Project URL"],
    )
    g.build()
