#!/usr/bin/env python3
"""
PR Block/Warn Report Generator - CLI

Generates a CSV report of PR scans that triggered action policy enforcement
(block or warn) across a namespace. Uses endorctl to query ScanResult and
Project resources.
"""

import subprocess
import json
import csv
import sys
import argparse
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


UI_BASE = "https://app.endorlabs.com"


def run_endorctl(args: List[str], namespace: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
    """Execute an endorctl command and return parsed JSON."""
    cmd = ["endorctl", "-n", namespace] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing: {' '.join(cmd)}")
        print(f"stderr: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        print(f"Timeout executing: {' '.join(cmd)}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def get_enforced_scan_results(namespace: str, days: int) -> List[Dict[str, Any]]:
    """Fetch ScanResults that have blocking or warning findings."""
    print(f"Fetching ScanResults with block/warn findings (last {days} days)...")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    filter_expr = (
        "(spec.blocking_findings exists or spec.warning_findings exists)"
        ' and context.type == "CONTEXT_TYPE_CI_RUN"'
        f' and meta.create_time > date("{cutoff}")'
    )

    response = run_endorctl(
        [
            "api", "list", "-r", "ScanResult",
            "--filter", filter_expr,
            "--field-mask", (
                "uuid,"
                "meta.create_time,"
                "meta.parent_uuid,"
                "meta.tags,"
                "tenant_meta.namespace,"
                "context.tags,"
                "spec.status,"
                "spec.blocking_findings,"
                "spec.warning_findings"
            ),
            "--sort-path", "meta.create_time",
            "--sort-order", "descending",
            "--list-all",
            "--traverse",
            "-t", "300s",
        ],
        namespace,
        timeout=360,
    )

    if not response:
        return []

    objects = response.get("list", {}).get("objects", [])
    print(f"Found {len(objects)} ScanResults with block/warn findings")
    return objects


def extract_pr_number(scan_result: Dict[str, Any]) -> Optional[str]:
    """Extract PR number from context.tags or meta.tags (e.g. 'pr=1')."""
    for tag_source in [scan_result.get("context", {}).get("tags", []),
                       scan_result.get("meta", {}).get("tags", [])]:
        for tag in tag_source:
            if tag.startswith("pr="):
                return tag.split("=", 1)[1]
    return None


def get_project_info(namespace: str, project_uuids: List[str]) -> Dict[str, Dict[str, str]]:
    """Resolve project UUIDs to full_name and http_clone_url."""
    if not project_uuids:
        return {}

    print(f"Resolving info for {len(project_uuids)} projects...")
    uuid_list = "', '".join(project_uuids)
    response = run_endorctl(
        [
            "api", "list", "-r", "Project",
            "--filter", f"uuid in ['{uuid_list}']",
            "--field-mask", "uuid,tenant_meta.namespace,spec.git.full_name,spec.git.http_clone_url",
            "--list-all",
            "--traverse",
        ],
        namespace,
        timeout=120,
    )

    if not response:
        return {}

    projects = {}
    for obj in response.get("list", {}).get("objects", []):
        git = obj.get("spec", {}).get("git", {})
        clone_url = git.get("http_clone_url", "")
        # Strip .git suffix for clean PR URLs
        base_url = clone_url.rstrip("/").removesuffix(".git") if clone_url else ""
        projects[obj.get("uuid", "")] = {
            "full_name": git.get("full_name", "Unknown"),
            "base_url": base_url,
            "namespace": obj.get("tenant_meta", {}).get("namespace", ""),
        }

    return projects


def build_pr_url(base_url: str, pr_number: Optional[str]) -> str:
    """Construct PR URL from project base URL and PR number."""
    if not base_url or not pr_number:
        return "N/A"
    return f"{base_url}/pull/{pr_number}"


BRAND = {
    "green": "#00D26A",
    "dark": "#1A1A2E",
    "block": "#d32f2f",
    "warn": "#fbc02d",
    "text_primary": "#1A1A2E",
    "text_secondary": "#5A6577",
    "white": "#FFFFFF",
    "table_header_bg": "#1A1A2E",
    "table_header_text": "#FFFFFF",
    "table_row_alt": "#F8F9FA",
    "table_border": "#DEE2E6",
}


def _fig_to_rl_image(fig, width: float, height: float) -> RLImage:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


def _build_timeline_chart(df: pd.DataFrame, page_width: float) -> RLImage:
    chart_df = df.copy()
    chart_df["day"] = chart_df["date"].dt.date
    daily = chart_df.groupby(["day", "outcome"]).size().reset_index(name="count")
    pivot = daily.pivot(index="day", columns="outcome", values="count").fillna(0)
    pivot.index = pd.to_datetime(pivot.index)

    fig, ax = plt.subplots(figsize=(page_width / 72, 2.8))
    fig.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])

    bottom = None
    for outcome, color in [("block", BRAND["block"]), ("warn", BRAND["warn"])]:
        if outcome in pivot.columns:
            vals = pivot[outcome].values
            ax.bar(pivot.index, vals, width=0.8, bottom=bottom,
                   color=color, label=outcome, edgecolor="none")
            bottom = vals if bottom is None else bottom + vals

    ax.set_ylabel("Count", fontsize=9, color=BRAND["text_secondary"])
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", linestyle="-", alpha=0.15, color="#AAAAAA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(colors=BRAND["text_secondary"], labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    fig.tight_layout()
    return _fig_to_rl_image(fig, page_width, 2.8 * 72)


def write_pdf(rows: List[Dict[str, Any]], namespace: str, days: int, filename: str) -> None:
    """Generate a branded PDF report from report rows."""
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date", ascending=False).reset_index(drop=True)

    page_w, page_h = landscape(letter)
    margin = 0.6 * inch
    usable_width = page_w - 2 * margin
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter),
                            leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"],
                              fontSize=20, textColor=HexColor(BRAND["dark"]), spaceAfter=4))
    styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"],
                              fontSize=10, textColor=HexColor(BRAND["text_secondary"]), spaceAfter=12))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"],
                              fontSize=13, textColor=HexColor(BRAND["dark"]),
                              spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle("CellText", parent=styles["Normal"], fontSize=7, leading=9))

    elements = []

    # Header
    elements.append(Paragraph("PR Block/Warn Report", styles["Title2"]))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(
        f"Namespace: {namespace}  |  Lookback: {days} days  |  Generated: {ts}",
        styles["Subtitle"]))

    # Green divider
    divider = Table([[""]], colWidths=[usable_width], rowHeights=[3])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["green"]))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    # Summary cards
    total = len(df)
    blocked = len(df[df["outcome"] == "block"])
    warned = len(df[df["outcome"] == "warn"])
    projects_affected = df["project_name"].nunique()

    summary_data = [
        ["Total Block/Warn PRs", "Blocked", "Warned", "Projects Affected"],
        [str(total), str(blocked), str(warned), str(projects_affected)],
    ]
    col_w = usable_width / 4
    summary_table = Table(summary_data, colWidths=[col_w] * 4, rowHeights=[20, 32])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["text_secondary"])),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("TEXTCOLOR", (0, 1), (-1, 1), HexColor(BRAND["text_primary"])),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(BRAND["table_row_alt"])),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor(BRAND["table_border"])),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Timeline chart
    if not df.empty and df["date"].notna().any():
        elements.append(Paragraph("Timeline", styles["SectionHeader"]))
        elements.append(_build_timeline_chart(df, usable_width))
        elements.append(Spacer(1, 8))

    # Top projects
    top_projects = (
        df.groupby("project_name")["outcome"]
        .value_counts()
        .unstack(fill_value=0)
        .assign(total=lambda x: x.sum(axis=1))
        .sort_values("total", ascending=False)
        .head(15)
    )
    if not top_projects.empty:
        elements.append(Paragraph("Top Projects by Block/Warn Count", styles["SectionHeader"]))
        tp_rows = [["Project", "Block", "Warn", "Total"]]
        for proj_name, row in top_projects.iterrows():
            tp_rows.append([
                Paragraph(str(proj_name), styles["CellText"]),
                str(int(row.get("block", 0))),
                str(int(row.get("warn", 0))),
                str(int(row.get("total", 0))),
            ])
        tp_col_widths = [usable_width * 0.6, usable_width * 0.13, usable_width * 0.13, usable_width * 0.14]
        tp_table = Table(tp_rows, colWidths=tp_col_widths, repeatRows=1)
        tp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor(BRAND["white"]), HexColor(BRAND["table_row_alt"])]),
        ]))
        elements.append(tp_table)
        elements.append(Spacer(1, 12))

    # Detail table
    elements.append(Paragraph("PR Scan Details", styles["SectionHeader"]))
    detail_rows = [["Date", "Project", "PR URL", "Scan Result", "Outcome", "Blockers", "Warnings"]]
    for _, row in df.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["date"]) else ""
        detail_rows.append([
            date_str,
            Paragraph(str(row["project_name"]), styles["CellText"]),
            Paragraph(str(row["pr_url"]), styles["CellText"]),
            Paragraph(str(row["scan_result_url"]), styles["CellText"]),
            row["outcome"],
            str(row["blocker_findings"]),
            str(row["warning_findings"]),
        ])
    detail_col_widths = [
        usable_width * 0.11, usable_width * 0.20, usable_width * 0.25,
        usable_width * 0.25, usable_width * 0.07, usable_width * 0.06, usable_width * 0.06,
    ]
    detail_table = Table(detail_rows, colWidths=detail_col_widths, repeatRows=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(BRAND["table_header_bg"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor(BRAND["table_header_text"])),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (4, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor(BRAND["table_border"])),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor(BRAND["white"]), HexColor(BRAND["table_row_alt"])]),
    ]))
    elements.append(detail_table)

    doc.build(elements)
    print(f"PDF report generated: {filename}")


def generate_report(namespace: str, days: int, outcome_filter: str, pdf: bool) -> None:
    """Main report generation logic."""
    # Step 1: Get ScanResults with block/warn (small, targeted query)
    scan_results = get_enforced_scan_results(namespace, days)
    if not scan_results:
        print("No ScanResults with block/warn findings found.")
        return

    # Step 2: Collect project UUIDs and resolve in bulk
    project_uuids = list(set(
        sr.get("meta", {}).get("parent_uuid", "")
        for sr in scan_results
        if sr.get("meta", {}).get("parent_uuid")
    ))
    project_info = get_project_info(namespace, project_uuids)

    # Step 3: Build report rows
    rows = []
    for sr in scan_results:
        sr_uuid = sr.get("uuid", "")
        meta = sr.get("meta", {})
        spec = sr.get("spec", {})
        project_uuid = meta.get("parent_uuid", "")
        proj = project_info.get(project_uuid, {"full_name": "Unknown", "base_url": "", "namespace": ""})

        # Use the project's namespace for URLs (correct for child namespaces)
        ns = proj["namespace"] or sr.get("tenant_meta", {}).get("namespace", namespace)

        blocking = spec.get("blocking_findings", [])
        warning = spec.get("warning_findings", [])
        outcome = "block" if blocking else "warn"

        # Apply outcome filter
        if outcome_filter != "all" and outcome != outcome_filter:
            continue

        pr_number = extract_pr_number(sr)

        rows.append({
            "date": meta.get("create_time", ""),
            "project_name": proj["full_name"],
            "project_url": f"{UI_BASE}/t/{ns}/projects/{project_uuid}",
            "pr_url": build_pr_url(proj["base_url"], pr_number),
            "scan_result_url": f"{UI_BASE}/t/{ns}/scan-history/{sr_uuid}",
            "outcome": outcome,
            "blocker_findings": len(blocking),
            "warning_findings": len(warning),
            "pr_check_conclusion": spec.get("status", ""),
        })

    if not rows:
        print("No PR scans matching the specified criteria.")
        return

    # Write CSV
    os.makedirs("generated_reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"generated_reports/pr_block_warn_{namespace}_{timestamp}.csv"

    fieldnames = [
        "date", "project_name", "project_url", "pr_url", "scan_result_url",
        "outcome", "blocker_findings", "warning_findings", "pr_check_conclusion",
    ]

    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV report generated: {csv_filename}")
    print(f"Total PR scans with block/warn: {len(rows)}")
    print(f"  Blocked: {sum(1 for r in rows if r['outcome'] == 'block')}")
    print(f"  Warned:  {sum(1 for r in rows if r['outcome'] == 'warn')}")

    if pdf:
        pdf_filename = f"generated_reports/pr_block_warn_{namespace}_{timestamp}.pdf"
        write_pdf(rows, namespace, days, pdf_filename)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a report of PR scans that were blocked or warned by action policies"
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace/tenant to query")
    parser.add_argument(
        "--days", type=int, default=21,
        help="Number of days to look back (default: 21)"
    )
    parser.add_argument(
        "--outcome", choices=["all", "block", "warn"], default="all",
        help="Filter by outcome: all (default), block, or warn"
    )
    parser.add_argument(
        "--pdf", action="store_true",
        help="Also generate a PDF report alongside the CSV"
    )
    args = parser.parse_args()

    print(f"PR Block/Warn Report")
    print(f"Namespace: {args.namespace}")
    print(f"Lookback:  {args.days} days")
    print(f"Outcome:   {args.outcome}")
    print("-" * 50)

    if args.days > 21:
        print("INFO: PR scan results are retained for 3 weeks (21 days).")
        print(f"      Requesting {args.days} days, but results beyond 21 days may not be available.\n")

    # Check endorctl availability
    try:
        subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.")
        sys.exit(1)

    generate_report(args.namespace, args.days, args.outcome, args.pdf)
    print("\nDone!")


if __name__ == "__main__":
    main()
