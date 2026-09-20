from __future__ import annotations

from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import TableStyle

BRAND = {
    "green": "#00D26A",
    "dark": "#1A1A2E",
    "dark_secondary": "#2D2D44",
    "critical": "#7B2D26",
    "high": "#C4532D",
    "medium": "#E8963F",
    "low": "#F0C75E",
    "newly_discovered": "#C4532D",
    "resolved": "#00D26A",
    "avg_line": "#3D6B8E",
    "min_line": "#5A9A7A",
    "max_line": "#C4532D",
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
    "warn": "#E8963F",
    "block": "#7B2D26",
}

FOOTER_LEFT = "Endor Labs · Block Mode Readiness"
PREPARED_BY = "Customer Success Engineering"


def add_page_footer(canvas, doc) -> None:
    canvas.saveState()
    page_w, _page_h = doc.pagesize
    canvas.setStrokeColor(HexColor(BRAND["green"]))
    canvas.setLineWidth(1.5)
    canvas.line(inch, 0.5 * inch, page_w - inch, 0.5 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(HexColor(BRAND["text_muted"]))
    canvas.drawRightString(page_w - inch, 0.35 * inch, f"Page {doc.page}")
    canvas.drawString(inch, 0.35 * inch, FOOTER_LEFT)
    canvas.restoreState()


def paragraph_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "BmrTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=HexColor(BRAND["dark"]),
            spaceAfter=8,
            fontName="Helvetica-Bold",
            leading=26,
        ),
        "subtitle": ParagraphStyle(
            "BmrSubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=HexColor(BRAND["text_secondary"]),
            spaceAfter=6,
            leading=14,
        ),
        "section": ParagraphStyle(
            "BmrSection",
            parent=base["Heading2"],
            fontSize=14,
            textColor=HexColor(BRAND["dark"]),
            spaceBefore=4,
            spaceAfter=8,
            fontName="Helvetica-Bold",
            leading=18,
        ),
        "body": ParagraphStyle(
            "BmrBody",
            parent=base["Normal"],
            fontSize=9,
            textColor=HexColor(BRAND["text_primary"]),
            spaceAfter=6,
            leading=12,
        ),
        "meta_label": ParagraphStyle(
            "BmrMetaLabel",
            parent=base["Normal"],
            fontSize=8,
            textColor=HexColor(BRAND["text_muted"]),
            leading=10,
        ),
        "meta_value": ParagraphStyle(
            "BmrMetaValue",
            parent=base["Normal"],
            fontSize=10,
            textColor=HexColor(BRAND["text_primary"]),
            leading=13,
            fontName="Helvetica-Bold",
        ),
        "card_label": ParagraphStyle(
            "BmrCardLabel",
            parent=base["Normal"],
            fontSize=7,
            textColor=HexColor(BRAND["text_secondary"]),
            leading=9,
        ),
        "card_value": ParagraphStyle(
            "BmrCardValue",
            parent=base["Normal"],
            fontSize=14,
            textColor=HexColor(BRAND["text_primary"]),
            fontName="Helvetica-Bold",
            leading=16,
        ),
        "cell": ParagraphStyle(
            "BmrCell",
            parent=base["Normal"],
            fontSize=8,
            textColor=HexColor(BRAND["text_primary"]),
            leading=10,
        ),
        "cell_header": ParagraphStyle(
            "BmrCellHeader",
            parent=base["Normal"],
            fontSize=8,
            textColor=HexColor(BRAND["table_header_text"]),
            fontName="Helvetica-Bold",
            leading=10,
        ),
    }


def branded_table_style(row_count: int) -> TableStyle:
    commands: List[Any] = [
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), HexColor(BRAND["text_primary"])),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]
    for i in range(1, row_count):
        if i % 2 == 0:
            commands.append(
                ("BACKGROUND", (0, i), (-1, i), HexColor(BRAND["table_row_alt"]))
            )
    return TableStyle(commands)
