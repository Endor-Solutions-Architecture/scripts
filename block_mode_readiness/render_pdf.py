from __future__ import annotations

import os
import tempfile
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
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

from analyze import Analysis
from brand import (
    BRAND,
    PREPARED_BY,
    add_page_footer,
    branded_table_style,
    paragraph_styles,
)
from snapshot import Snapshot

LOGO_PATH = Path(__file__).resolve().parent / "endor-logo.svg"
MAX_REPO_ROWS = 20
MAX_TRAJECTORY_ROWS = 15
SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _fmt_pct_denom(value: Optional[float], n: int, d: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}% ({n} / {d})"


def _fmt_generated_at(value: str) -> str:
    if not value:
        return "n/a"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return value


def _logo_flowable() -> Optional[Image]:
    try:
        import cairosvg
    except ImportError:
        return None
    if not LOGO_PATH.is_file():
        return None
    try:
        png = cairosvg.svg2png(url=str(LOGO_PATH), output_width=800, output_height=80)
    except Exception:
        return None
    return Image(BytesIO(png), width=3.0 * inch, height=0.3 * inch)


def _section_header(title: str, styles: Dict[str, Any]) -> Paragraph:
    return Paragraph(
        f'<font color="{BRAND["green"]}">|</font>&nbsp;&nbsp;{title}',
        styles["section"],
    )


def _summary_cards(
    items: Sequence[Tuple[str, str]], page_w: float, styles: Dict[str, Any]
) -> Table:
    n = len(items)
    col_w = page_w / n
    cards = []
    for label, value in items:
        inner = Table(
            [
                [Paragraph(label, styles["card_label"])],
                [Paragraph(value, styles["card_value"])],
            ],
            colWidths=[col_w - 8],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["card_bg"])),
                    ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["card_border"])),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (0, 0), 8),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEABOVE", (0, 0), (-1, 0), 3, HexColor(BRAND["green"])),
                ]
            )
        )
        cards.append(inner)
    row = Table([cards], colWidths=[col_w] * n)
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return row


def _branded_table(headers: List[str], rows: List[List[str]], col_widths: List[float]):
    data = [headers] + rows
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(branded_table_style(len(data)))
    return table


def _daily_timeline(snapshot: Snapshot, page_w: float) -> Optional[Image]:
    checks: Counter[str] = Counter()
    warns: Counter[str] = Counter()
    for scan in snapshot.scans.values():
        day = scan.create_time[:10]
        checks[day] += 1
        if scan.outcome == "warn":
            warns[day] += 1
    days = sorted(set(checks) | set(warns))
    if not days:
        return None
    xs = [datetime.fromisoformat(day) for day in days]
    fig, ax = plt.subplots(figsize=(page_w / 72.0, 2.2))
    fig.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])
    ax.plot(
        xs,
        [checks[d] for d in days],
        color=BRAND["avg_line"],
        marker="o",
        label="PR checks",
    )
    ax.plot(
        xs,
        [warns[d] for d in days],
        color=BRAND["warn"],
        marker="s",
        label="Warns",
    )
    ax.set_ylabel("Count", fontsize=8, color=BRAND["text_secondary"])
    ax.tick_params(colors=BRAND["text_secondary"], labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    ax.legend(fontsize=7, frameon=False)
    fig.autofmt_xdate()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=page_w, height=2.1 * inch)


def _cover(analysis: Analysis, snapshot: Snapshot, styles: Dict[str, Any], page_w: float):
    elements: List[Any] = []
    logo = _logo_flowable()
    if logo is not None:
        elements.append(logo)
    else:
        elements.append(Paragraph("Endor Labs", styles["title"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Block Mode Readiness", styles["title"]))
    elements.append(
        Paragraph("Warn-to-block readiness for a tagged project set", styles["subtitle"])
    )
    elements.append(Spacer(1, 10))
    divider = Table([[""]], colWidths=[page_w], rowHeights=[3])
    divider.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["green"])),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(divider)
    elements.append(Spacer(1, 16))

    tags = ", ".join(snapshot.meta.project_tags) or "n/a"
    window = f"{analysis.window_start} – {analysis.window_end}"
    decision = snapshot.meta.decision_date or "Not set"
    meta_rows = [
        [
            Paragraph("Prepared for", styles["meta_label"]),
            Paragraph(snapshot.meta.customer or snapshot.meta.namespace, styles["meta_value"]),
            Paragraph("Prepared by", styles["meta_label"]),
            Paragraph(PREPARED_BY, styles["meta_value"]),
        ],
        [
            Paragraph("Namespace", styles["meta_label"]),
            Paragraph(snapshot.meta.namespace, styles["meta_value"]),
            Paragraph("Project tags", styles["meta_label"]),
            Paragraph(tags, styles["meta_value"]),
        ],
        [
            Paragraph("Window", styles["meta_label"]),
            Paragraph(window, styles["meta_value"]),
            Paragraph("Generated at", styles["meta_label"]),
            Paragraph(_fmt_generated_at(snapshot.meta.generated_at), styles["meta_value"]),
        ],
        [
            Paragraph("Decision date", styles["meta_label"]),
            Paragraph(decision, styles["meta_value"]),
            Paragraph("Lookback requested", styles["meta_label"]),
            Paragraph(f"{snapshot.meta.days} days", styles["meta_value"]),
        ],
    ]
    meta = Table(meta_rows, colWidths=[page_w * 0.18, page_w * 0.32, page_w * 0.20, page_w * 0.30])
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["card_bg"])),
                ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["card_border"])),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(meta)
    if snapshot.policies:
        names = ", ".join(policy.name for policy in snapshot.policies if policy.name)
        if names:
            elements.append(Spacer(1, 12))
            elements.append(
                Paragraph(
                    f"Action policies that apply to this rollout: {names}.",
                    styles["body"],
                )
            )
    return elements


def _how_to_use(styles: Dict[str, Any]) -> List[Any]:
    return [
        _section_header("How to use this report", styles),
        Paragraph(
            "Decision owner: stay with this PDF for headline rates, caveats, "
            "concentration, and developer-response mix.",
            styles["body"],
        ),
        Paragraph(
            "Security engineering: label <b>fp</b> and <b>reason</b> in "
            "fp_worksheet.csv and return the file.",
            styles["body"],
        ),
        Paragraph(
            "Engineering: use pr_trajectories.csv and the repository ranking "
            "to see where friction will land.",
            styles["body"],
        ),
        Paragraph(
            "Operator: re-run the CLI. Snapshots and CSVs are the durable record; "
            "this PDF is the meeting artifact.",
            styles["body"],
        ),
        Spacer(1, 8),
        Paragraph("Output files", styles["subtitle"]),
        Paragraph("readiness_report.pdf — this pack.", styles["body"]),
        Paragraph("pr_checks.csv — every PR check, including clean.", styles["body"]),
        Paragraph(
            "fp_worksheet.csv — one row per warning finding; blank fp / reason until labeled.",
            styles["body"],
        ),
        Paragraph(
            "pr_trajectories.csv — rescan sequence for every PR that warned at least once.",
            styles["body"],
        ),
        Paragraph("summary.json — headline numbers for week-over-week comparison.", styles["body"]),
    ]


def _caveats(analysis: Analysis, snapshot: Snapshot, styles: Dict[str, Any]) -> List[Any]:
    elements: List[Any] = [
        _section_header("Caveats", styles),
        Paragraph(
            "Rates use only tagged projects (project tags, not finding tags). "
            "They do not describe the whole tenant.",
            styles["body"],
        ),
        Paragraph(
            "Mark-dates split the window when coverage changed mid-window. "
            "Every percentage is shown with its denominator and sample size.",
            styles["body"],
        ),
        Paragraph(
            "Warn mode does not stop merges. Section D measures rescan response "
            "on later PR checks, not merge behaviour. A single-scan PR is not "
            "treated as ignored.",
            styles["body"],
        ),
    ]
    if analysis.snapshot_count > 1:
        pack = (
            f"ScanResults are retained for 21 days. This pack is "
            f"{analysis.snapshot_count} weekly snapshots."
        )
    else:
        pack = (
            "ScanResults are retained for 21 days. This pack is one weekly snapshot. "
            "Collect weekly so history outlives API retention."
        )
    history = (
        f" History starts at {analysis.history_starts_at}, the first scan date "
        "in the available snapshots, not at an assumed rollout start."
    )
    elements.append(Paragraph(pack + history, styles["body"]))
    if analysis.gate1_per_finding is None:
        elements.append(
            Paragraph(
                "The false-positive rate is blocked on returned labels. "
                f"Sample size: {len(analysis.fp_rows)} warning findings in "
                "fp_worksheet.csv.",
                styles["body"],
            )
        )
    if analysis.policy_fallback:
        elements.append(
            Paragraph(
                "The policy column is the violation type when a scan does not "
                "name a policy.",
                styles["body"],
            )
        )
    if snapshot.meta.ci_runs_dropped_no_pr:
        elements.append(
            Paragraph(
                f"{snapshot.meta.ci_runs_dropped_no_pr} CI runs without a pr= tag "
                "were counted as dropped and are excluded from sections A–D.",
                styles["body"],
            )
        )
    if snapshot.meta.days > 21:
        elements.append(
            Paragraph(
                f"Lookback requested was {snapshot.meta.days} days; the API retains "
                "21 days. Snapshots are the real history.",
                styles["body"],
            )
        )
    return elements


def _section_a(
    analysis: Analysis, snapshot: Snapshot, styles: Dict[str, Any], page_w: float
) -> List[Any]:
    pct = _fmt_pct(analysis.would_have_blocked_pct)
    denom = f"{analysis.checks_warn} / {analysis.checks_total}"
    cards = _summary_cards(
        [
            ("PR checks (denominator)", str(analysis.checks_total)),
            ("Warns", str(analysis.checks_warn)),
            ("Would-have-blocked", f"{pct} ({denom})"),
            ("Tagged projects", str(len(analysis.repos))),
        ],
        page_w,
        styles,
    )
    elements: List[Any] = [
        _section_header("A — Would-have-blocked", styles),
        Paragraph(
            "Denominator is every PR check on tagged projects in the window. "
            "Numerator is outcome warn. Blocks are listed separately if any.",
            styles["body"],
        ),
        cards,
        Spacer(1, 10),
    ]
    if analysis.checks_block:
        elements.append(
            Paragraph(
                f"Blocking outcomes in this window: {analysis.checks_block} of "
                f"{analysis.checks_total}.",
                styles["body"],
            )
        )
    type_rows = [
        [
            row.violation_type,
            str(row.checks_with_type),
            _fmt_pct_denom(row.rate, row.checks_with_type, analysis.checks_total),
        ]
        for row in analysis.by_violation_type
    ]
    if type_rows:
        elements.append(Paragraph("By violation type", styles["subtitle"]))
        elements.append(
            _branded_table(
                ["Violation type", "Checks with type", "Rate"],
                type_rows,
                [page_w * 0.40, page_w * 0.30, page_w * 0.30],
            )
        )
        elements.append(Spacer(1, 10))
    mark_rows = []
    for split in analysis.mark_splits:
        mark_rows.append(
            [
                split.key,
                split.date,
                f"{split.before_warn} / {split.before_total}",
                f"{split.after_warn} / {split.after_total}",
            ]
        )
    if mark_rows:
        elements.append(Paragraph("Before / after mark-dates", styles["subtitle"]))
        elements.append(
            _branded_table(
                ["Mark", "Date", "Before (warn / total)", "After (warn / total)"],
                mark_rows,
                [page_w * 0.20, page_w * 0.20, page_w * 0.30, page_w * 0.30],
            )
        )
        elements.append(Spacer(1, 10))
    timeline = _daily_timeline(snapshot, page_w)
    if timeline is not None:
        elements.append(Paragraph("Daily PR checks vs warns", styles["subtitle"]))
        elements.append(timeline)
    return elements


def _section_b(analysis: Analysis, styles: Dict[str, Any], page_w: float) -> List[Any]:
    n = len(analysis.repos)
    elements: List[Any] = [
        _section_header("B — Concentration", styles),
        Paragraph(
            f"{analysis.zero_warn_repos} of {n} tagged projects had zero warns. "
            f"The top handful account for {_fmt_pct(analysis.top_repo_warn_share)} "
            "of warns.",
            styles["body"],
        ),
    ]
    shown = analysis.repos[:MAX_REPO_ROWS]
    if n > MAX_REPO_ROWS:
        elements.append(
            Paragraph(
                f"Showing the top {len(shown)} of {n} repositories by warn count. "
                "The full ranking is in pr_checks.csv plus the project list.",
                styles["body"],
            )
        )
    rows = [
        [row.project_name, str(row.checks), str(row.warns), _fmt_pct(row.rate)]
        for row in shown
    ]
    if rows:
        elements.append(
            _branded_table(
                ["Repository", "Checks", "Warns", "Rate"],
                rows,
                [page_w * 0.46, page_w * 0.18, page_w * 0.18, page_w * 0.18],
            )
        )
    return elements


def _section_c(analysis: Analysis, styles: Dict[str, Any], page_w: float) -> List[Any]:
    elements: List[Any] = [
        _section_header("C — Findings to label", styles),
        Paragraph(
            "One row per warning finding is in fp_worksheet.csv. Security labels "
            "fp and reason and returns the file. Gate 1 is computed only from "
            "returned yes/no labels.",
            styles["body"],
        ),
    ]
    types = sorted(analysis.finding_counts_by_type_severity)
    if types:
        headers = ["Violation type"] + list(SEVERITY_ORDER) + ["Total"]
        rows = []
        for vtype in types:
            counts = analysis.finding_counts_by_type_severity[vtype]
            cells = [str(counts.get(sev, 0)) for sev in SEVERITY_ORDER]
            total = sum(counts.get(sev, 0) for sev in counts)
            rows.append([vtype] + cells + [str(total)])
        col_w = page_w / 6
        elements.append(Paragraph("Warning findings by type and severity", styles["subtitle"]))
        elements.append(
            _branded_table(headers, rows, [col_w * 1.4] + [col_w * 0.92] * 5)
        )
        elements.append(Spacer(1, 10))
    if analysis.gate1_per_finding is None:
        elements.append(
            Paragraph(
                "Gate 1 is awaiting returned labels. The false-positive rate is "
                f"blocked on returned labels (sample size {len(analysis.fp_rows)}).",
                styles["body"],
            )
        )
    else:
        elements.append(
            Paragraph(
                f"Gate 1 per finding: {_fmt_pct(analysis.gate1_per_finding)}. "
                f"Gate 1 per PR: {_fmt_pct(analysis.gate1_per_pr)}.",
                styles["body"],
            )
        )
        if analysis.gate1_by_type:
            type_bits = ", ".join(
                f"{name} {_fmt_pct(rate)}"
                for name, rate in analysis.gate1_by_type.items()
            )
            elements.append(Paragraph(f"By violation type: {type_bits}.", styles["body"]))
    if analysis.unmatched_labels:
        elements.append(
            Paragraph(
                f"{len(analysis.unmatched_labels)} label rows did not join a "
                "worksheet finding and are listed, not dropped from the sample "
                "in silence.",
                styles["body"],
            )
        )
        shown = analysis.unmatched_labels[:MAX_REPO_ROWS]
        rows = [
            [
                str(row.get("finding_uuid", "")),
                str(row.get("scan_result_uuid", "")),
            ]
            for row in shown
        ]
        if len(analysis.unmatched_labels) > MAX_REPO_ROWS:
            elements.append(
                Paragraph(
                    f"Showing {len(shown)} of {len(analysis.unmatched_labels)} "
                    "unmatched label rows.",
                    styles["body"],
                )
            )
        elements.append(
            _branded_table(
                ["finding_uuid", "scan_result_uuid"],
                rows,
                [page_w * 0.50, page_w * 0.50],
            )
        )
    return elements


def _section_d(analysis: Analysis, styles: Dict[str, Any], page_w: float) -> List[Any]:
    elements: List[Any] = [
        _section_header("D — Developer response", styles),
        Paragraph(
            "Endor-only, per PR that warned at least once. Acted means a later "
            "scan on the same PR had a strictly lower warning count. Cleared is "
            "the acted subset that reached zero warnings. Still-open did not drop. "
            "Single-scan has only one scan in the available history.",
            styles["body"],
        ),
        _summary_cards(
            [
                ("Acted", str(analysis.d_acted)),
                ("Still open", str(analysis.d_still_open)),
                ("Single scan", str(analysis.d_single_scan)),
                ("Cleared", str(analysis.d_cleared)),
            ],
            page_w,
            styles,
        ),
        Spacer(1, 10),
    ]
    shown = analysis.trajectories[:MAX_TRAJECTORY_ROWS]
    rest = len(analysis.trajectories) - len(shown)
    if rest > 0:
        elements.append(
            Paragraph(
                f"Showing {len(shown)} of {len(analysis.trajectories)} warned PRs. "
                "The rest are in pr_trajectories.csv.",
                styles["body"],
            )
        )
    else:
        elements.append(
            Paragraph(
                f"{analysis.d_warned_prs} warned PRs. Full sequences are also in "
                "pr_trajectories.csv.",
                styles["body"],
            )
        )
    rows = [
        [
            row.project_name,
            f"#{row.pr_number}" if row.pr_number else "",
            row.sequence,
            row.classification,
        ]
        for row in shown
    ]
    if rows:
        elements.append(
            _branded_table(
                ["Repository", "PR", "Sequence", "Classification"],
                rows,
                [page_w * 0.34, page_w * 0.12, page_w * 0.28, page_w * 0.26],
            )
        )
    return elements


def _next_steps(analysis: Analysis, snapshot: Snapshot, styles: Dict[str, Any]) -> List[Any]:
    elements: List[Any] = [
        _section_header("Next steps", styles),
        Paragraph(
            "Return the labeled fp_worksheet.csv so Gate 1 can be computed from "
            "yes/no labels.",
            styles["body"],
        ),
        Paragraph(
            "Collect weekly from the first week of warn mode. Do not delete old "
            "snapshot folders. Decision-week reporting unions the directory.",
            styles["body"],
        ),
    ]
    if snapshot.meta.decision_date:
        elements.append(
            Paragraph(
                f"This pack informs the decision on {snapshot.meta.decision_date}.",
                styles["body"],
            )
        )
    else:
        elements.append(
            Paragraph(
                "Set a decision date on the next collect when the rollout owner "
                "has one.",
                styles["body"],
            )
        )
    elements.append(
        Paragraph(
            f"Window covered: {analysis.window_start} to {analysis.window_end}. "
            f"History starts at {analysis.history_starts_at}.",
            styles["body"],
        )
    )
    return elements


def write_pdf(analysis: Analysis, snapshot: Snapshot, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    page_w = letter[0] - 2 * inch
    styles = paragraph_styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        pageCompression=0,
    )
    story: List[Any] = []
    story.extend(_cover(analysis, snapshot, styles, page_w))
    story.append(PageBreak())
    story.extend(_how_to_use(styles))
    story.append(PageBreak())
    story.extend(_caveats(analysis, snapshot, styles))
    story.append(PageBreak())
    story.extend(_section_a(analysis, snapshot, styles, page_w))
    story.append(PageBreak())
    story.extend(_section_b(analysis, styles, page_w))
    story.append(PageBreak())
    story.extend(_section_c(analysis, styles, page_w))
    story.append(PageBreak())
    story.extend(_section_d(analysis, styles, page_w))
    story.append(PageBreak())
    story.extend(_next_steps(analysis, snapshot, styles))
    doc.build(story, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
