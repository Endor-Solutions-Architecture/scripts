from __future__ import annotations

import base64
import json
from collections import Counter
from dataclasses import asdict
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from analyze import Analysis, project_url
from brand import BRAND, PREPARED_BY
from snapshot import Snapshot

LOGO_PATH = Path(__file__).resolve().parent / "endor-logo.svg"


def _pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def _daily_rows(snapshot: Snapshot) -> List[Dict[str, Any]]:
    outcomes: Dict[str, Counter[str]] = {}
    for scan in snapshot.scans.values():
        day = scan.create_time[:10]
        outcomes.setdefault(day, Counter())
        outcomes[day]["checks"] += 1
        outcomes[day][scan.outcome] += 1

    if not outcomes:
        return []

    days = sorted(outcomes)
    try:
        first = date.fromisoformat(days[0])
        last = date.fromisoformat(days[-1])
        all_days: List[str] = []
        current = first
        while current <= last:
            all_days.append(current.isoformat())
            current += timedelta(days=1)
    except ValueError:
        all_days = days

    rows: List[Dict[str, Any]] = []
    for day in all_days:
        counts = outcomes.get(day, Counter())
        checks = counts["checks"]
        warns = counts["warn"]
        rows.append(
            {
                "date": day,
                "checks": checks,
                "clean": counts["clean"],
                "warn": warns,
                "block": counts["block"],
                "warn_rate": _pct(warns, checks),
            }
        )
    return rows


def _logo_data_uri() -> str:
    try:
        data = LOGO_PATH.read_bytes()
    except OSError:
        return ""
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def build_dashboard_payload(
    analysis: Analysis,
    snapshot: Snapshot,
) -> Dict[str, Any]:
    checks_clean = max(
        analysis.checks_total - analysis.checks_warn - analysis.checks_block,
        0,
    )
    projects_by_uuid = snapshot.projects
    repos: List[Dict[str, Any]] = []
    for row in analysis.repos:
        project = projects_by_uuid.get(row.project_uuid)
        namespace = project.namespace if project else snapshot.meta.namespace
        repos.append(
            {
                **asdict(row),
                "project_url": project_url(namespace, row.project_uuid),
                "tags": list(project.tags) if project else [],
            }
        )

    mark_splits: List[Dict[str, Any]] = []
    for split in analysis.mark_splits:
        row = asdict(split)
        row["before_rate"] = _pct(split.before_warn, split.before_total)
        row["after_rate"] = _pct(split.after_warn, split.after_total)
        mark_splits.append(row)

    warning_findings_by_policy: Counter[str] = Counter()
    for row in analysis.fp_rows:
        policy = str(row.get("policy") or "Unattributed")
        warning_findings_by_policy[policy] += 1

    policies: List[Dict[str, Any]] = []
    for policy in snapshot.policies:
        policies.append(
            {
                **asdict(policy),
                "state": "disabled" if policy.disabled else "enabled",
                "warning_findings": warning_findings_by_policy.get(policy.name, 0),
            }
        )

    finding_counts = {
        violation_type: dict(severities)
        for violation_type, severities in analysis.finding_counts_by_type_severity.items()
    }
    labeled_finding_counts = (
        list(analysis.gate1_per_finding_counts)
        if analysis.gate1_per_finding_counts is not None
        else None
    )
    labeled_pr_counts = (
        list(analysis.gate1_per_pr_counts)
        if analysis.gate1_per_pr_counts is not None
        else None
    )

    caveats = [
        "Rates cover only the selected project tags, not the whole tenant.",
        "Warn mode does not stop merges. Developer behavior measures later Endor PR scans, not GitHub merge behavior.",
        (
            "ScanResults are retained for 21 days. Preserve weekly snapshots so "
            "the consolidated history outlives API retention."
        ),
        (
            f"{snapshot.meta.ci_runs_dropped_no_pr} CI runs without a pr= tag "
            "were excluded from readiness calculations."
        ),
    ]
    if analysis.gate1_per_finding_counts is None:
        caveats.append(
            "False-positive rates require returned labels in fp_worksheet.csv."
        )
    if analysis.policy_fallback:
        caveats.append(
            "At least one finding lacked ScanResult policy identity; its violation type is shown as the policy fallback."
        )

    return {
        "meta": {
            "customer": snapshot.meta.customer,
            "namespace": snapshot.meta.namespace,
            "project_tags": list(snapshot.meta.project_tags),
            "days": snapshot.meta.days,
            "mark_dates": dict(snapshot.meta.mark_dates),
            "decision_date": snapshot.meta.decision_date,
            "generated_at": snapshot.meta.generated_at,
            "window_start": analysis.window_start,
            "window_end": analysis.window_end,
            "history_starts_at": analysis.history_starts_at,
            "snapshot_count": analysis.snapshot_count,
            "project_count": snapshot.meta.project_count,
            "ci_runs_dropped_no_pr": snapshot.meta.ci_runs_dropped_no_pr,
            "prepared_by": PREPARED_BY,
        },
        "summary": {
            "checks_total": analysis.checks_total,
            "checks_clean": checks_clean,
            "checks_warn": analysis.checks_warn,
            "checks_block": analysis.checks_block,
            "would_have_blocked_pct": analysis.would_have_blocked_pct,
            "zero_warn_repos": analysis.zero_warn_repos,
            "top_repo_warn_share": analysis.top_repo_warn_share,
            "warned_prs": analysis.d_warned_prs,
            "warning_findings": len(analysis.fp_rows),
            "acted": analysis.d_acted,
            "still_open": analysis.d_still_open,
            "single_scan": analysis.d_single_scan,
            "cleared": analysis.d_cleared,
        },
        "daily": _daily_rows(snapshot),
        "by_violation_type": [asdict(row) for row in analysis.by_violation_type],
        "mark_splits": mark_splits,
        "repos": repos,
        "trajectories": [asdict(row) for row in analysis.trajectories],
        "pr_checks": [dict(row) for row in analysis.pr_check_rows],
        "findings": [dict(row) for row in analysis.fp_rows],
        "finding_counts_by_type_severity": finding_counts,
        "false_positives": {
            "available": analysis.gate1_per_finding_counts is not None,
            "per_finding_rate": analysis.gate1_per_finding,
            "per_finding_counts": labeled_finding_counts,
            "per_pr_rate": analysis.gate1_per_pr,
            "per_pr_counts": labeled_pr_counts,
            "by_type": analysis.gate1_by_type,
            "by_type_counts": analysis.gate1_by_type_counts,
            "by_type_per_pr": analysis.gate1_by_type_per_pr,
            "by_type_per_pr_counts": analysis.gate1_by_type_per_pr_counts,
            "unmatched_labels": [dict(row) for row in analysis.unmatched_labels],
        },
        "policies": policies,
        "caveats": caveats,
        "capabilities": {
            "pr_comments": False,
            "merge_status": False,
            "ci_duration": False,
            "remediation_status": False,
            "pilot_plan_progress": False,
        },
    }


def _encoded_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _document(payload: Dict[str, Any]) -> str:
    html = _HTML
    replacements = {
        "__DASHBOARD_DATA__": _encoded_payload(payload),
        "__LOGO_DATA_URI__": _logo_data_uri(),
        "__BRAND_GREEN__": BRAND["green"],
        "__BRAND_DARK__": BRAND["dark"],
        "__BRAND_DARK_SECONDARY__": BRAND["dark_secondary"],
        "__BRAND_CARD_BG__": BRAND["card_bg"],
        "__BRAND_CARD_BORDER__": BRAND["card_border"],
        "__BRAND_TEXT_PRIMARY__": BRAND["text_primary"],
        "__BRAND_TEXT_SECONDARY__": BRAND["text_secondary"],
        "__BRAND_TEXT_MUTED__": BRAND["text_muted"],
        "__BRAND_WHITE__": BRAND["white"],
        "__BRAND_WARN__": BRAND["warn"],
        "__BRAND_BLOCK__": BRAND["block"],
        "__PREPARED_BY__": escape(PREPARED_BY),
    }
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


def write_html(
    analysis: Analysis,
    snapshot: Snapshot,
    path: Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _document(build_dashboard_payload(analysis, snapshot)),
        encoding="utf-8",
    )
    return path


_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Block Mode Readiness Dashboard</title>
  <style>
    :root {
      --green: __BRAND_GREEN__;
      --dark: __BRAND_DARK__;
      --dark-2: __BRAND_DARK_SECONDARY__;
      --card: __BRAND_CARD_BG__;
      --border: __BRAND_CARD_BORDER__;
      --text: __BRAND_TEXT_PRIMARY__;
      --secondary: __BRAND_TEXT_SECONDARY__;
      --muted: __BRAND_TEXT_MUTED__;
      --white: __BRAND_WHITE__;
      --warn: __BRAND_WARN__;
      --block: __BRAND_BLOCK__;
      --shadow: 0 10px 32px rgba(26, 26, 46, 0.08);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: #f2f4f7;
      color: var(--text);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }
    a { color: #4937b8; text-decoration: none; }
    a:hover, a:focus { text-decoration: underline; }
    button, input, select { font: inherit; }
    button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible {
      outline: 3px solid rgba(0, 210, 106, 0.3);
      outline-offset: 2px;
    }

    .app-header {
      background: linear-gradient(120deg, var(--dark), #281752);
      color: var(--white);
      padding: 18px 28px 16px;
    }
    .header-row {
      align-items: center;
      display: flex;
      gap: 20px;
      justify-content: space-between;
    }
    .brand { align-items: center; display: flex; gap: 14px; min-width: 0; }
    .brand img { height: 26px; max-width: 190px; object-fit: contain; }
    .brand-copy { min-width: 0; }
    .brand-copy h1 { font-size: 20px; line-height: 1.2; margin: 0; }
    .brand-copy p {
      color: rgba(255,255,255,0.7);
      font-size: 12px;
      margin: 4px 0 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .generated {
      color: rgba(255,255,255,0.72);
      font-size: 11px;
      text-align: right;
      white-space: nowrap;
    }
    .snapshot-pill {
      background: rgba(0,210,106,0.14);
      border: 1px solid rgba(0,210,106,0.45);
      border-radius: 999px;
      color: #8ff0bd;
      display: inline-block;
      font-weight: 700;
      margin-top: 6px;
      padding: 3px 9px;
    }

    .tabs-shell {
      background: var(--white);
      border-bottom: 1px solid var(--border);
      box-shadow: 0 2px 8px rgba(26,26,46,0.04);
      overflow-x: auto;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .tabs {
      display: flex;
      gap: 2px;
      margin: 0 auto;
      max-width: 1440px;
      min-width: max-content;
      padding: 0 22px;
    }
    .tab-button {
      background: transparent;
      border: 0;
      border-bottom: 3px solid transparent;
      color: var(--secondary);
      cursor: pointer;
      font-size: 12px;
      padding: 14px 13px 11px;
    }
    .tab-button.active {
      border-bottom-color: #6f56d9;
      color: #4937b8;
      font-weight: 700;
    }

    main {
      margin: 0 auto;
      max-width: 1440px;
      padding: 28px;
    }
    .tab-panel[hidden] { display: none; }
    .section-heading { margin-bottom: 18px; }
    .section-heading h2 { font-size: 23px; margin: 0 0 4px; }
    .section-heading p { color: var(--secondary); margin: 0; }

    .card {
      background: var(--white);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
      padding: 20px;
    }
    .card h3 { font-size: 15px; margin: 0 0 14px; }
    .card-subtitle { color: var(--secondary); font-size: 12px; margin: -8px 0 16px; }
    .kpi-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      margin-bottom: 20px;
    }
    .kpi {
      background: var(--white);
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: 0 6px 18px rgba(26,26,46,0.05);
      min-height: 98px;
      padding: 16px;
    }
    .kpi-label {
      color: var(--secondary);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .kpi-value { font-size: 28px; font-weight: 750; line-height: 1.2; margin-top: 8px; }
    .kpi-detail { color: var(--muted); font-size: 11px; margin-top: 4px; }
    .green { color: #009d50; }
    .warn { color: #b86d13; }
    .block { color: var(--block); }

    .split-grid {
      display: grid;
      gap: 20px;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }
    .chart-wrap { min-height: 270px; position: relative; }
    canvas { display: block; height: 260px; max-width: 100%; width: 100%; }
    .bar-list { display: grid; gap: 12px; }
    .bar-row { display: grid; gap: 8px; grid-template-columns: minmax(105px, 180px) 1fr auto; align-items: center; }
    .bar-track { background: #eef0f4; border-radius: 999px; height: 12px; overflow: hidden; }
    .bar-fill { background: #6f56d9; border-radius: inherit; height: 100%; min-width: 2px; }
    .bar-label, .bar-value { font-size: 12px; }

    .notice {
      background: #f7f5ff;
      border-left: 4px solid #6f56d9;
      border-radius: 7px;
      color: var(--secondary);
      margin-bottom: 20px;
      padding: 13px 15px;
    }
    .notice strong { color: var(--text); }
    .caveats { margin: 0; padding-left: 20px; }
    .caveats li { margin: 8px 0; }

    .data-table-shell { overflow: hidden; padding: 0; }
    .table-controls {
      align-items: center;
      border-bottom: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 14px 16px;
    }
    .table-controls input, .table-controls select {
      background: var(--white);
      border: 1px solid #ccd2da;
      border-radius: 7px;
      color: var(--text);
      min-height: 36px;
      padding: 7px 10px;
    }
    .table-controls input { flex: 1 1 260px; min-width: 180px; }
    .table-controls select { max-width: 220px; }
    .table-scroller { overflow-x: auto; }
    table { border-collapse: collapse; min-width: 760px; width: 100%; }
    th {
      background: var(--dark);
      color: var(--white);
      font-size: 11px;
      letter-spacing: 0.02em;
      padding: 10px 12px;
      text-align: left;
      white-space: nowrap;
    }
    th button {
      background: transparent;
      border: 0;
      color: inherit;
      cursor: pointer;
      font-weight: 700;
      padding: 0;
    }
    td {
      border-bottom: 1px solid #e7eaf0;
      font-size: 12px;
      max-width: 360px;
      overflow-wrap: anywhere;
      padding: 9px 12px;
      vertical-align: top;
    }
    tbody tr:nth-child(even) { background: #f9fafb; }
    tbody tr:hover { background: #f2f7f5; }
    .table-footer {
      align-items: center;
      color: var(--secondary);
      display: flex;
      font-size: 12px;
      justify-content: space-between;
      padding: 12px 16px;
    }
    .pager { display: flex; gap: 7px; }
    .pager button {
      background: var(--white);
      border: 1px solid #ccd2da;
      border-radius: 6px;
      cursor: pointer;
      padding: 5px 10px;
    }
    .pager button:disabled { cursor: not-allowed; opacity: 0.45; }
    .empty-state { color: var(--muted); padding: 32px; text-align: center; }
    .badge {
      border-radius: 999px;
      display: inline-block;
      font-size: 10px;
      font-weight: 750;
      padding: 3px 8px;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .badge-clean, .badge-acted, .badge-yes { background: #dff7e9; color: #167345; }
    .badge-warn, .badge-single_scan, .badge-unsure { background: #fff0dc; color: #92540d; }
    .badge-block, .badge-still_open, .badge-no { background: #f8dfdc; color: #8c3027; }
    .badge-empty { background: #edf0f4; color: #687486; }

    .definition-grid {
      display: grid;
      gap: 15px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .definition {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 15px;
    }
    .definition h3 { margin: 0 0 7px; }
    .definition p { color: var(--secondary); margin: 0; }
    .footer-note { color: var(--muted); font-size: 11px; margin-top: 24px; text-align: center; }

    @media (max-width: 800px) {
      .app-header { padding: 15px 18px; }
      .header-row { align-items: flex-start; flex-direction: column; gap: 10px; }
      .generated { text-align: left; }
      main { padding: 18px 12px; }
      .split-grid { grid-template-columns: 1fr; }
      .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .bar-row { grid-template-columns: minmax(90px, 130px) 1fr; }
      .bar-value { grid-column: 2; }
    }
    @media (max-width: 440px) {
      .kpi-grid { grid-template-columns: 1fr; }
      .brand img { max-width: 145px; }
    }
    @media print {
      body { background: white; }
      .tabs-shell, .table-controls, .pager { display: none !important; }
      .tab-panel[hidden] { display: block; }
      .tab-panel { break-before: page; }
      .tab-panel:first-of-type { break-before: auto; }
      .card, .kpi { box-shadow: none; }
      main { max-width: none; padding: 16px; }
    }
  </style>
</head>
<body>
  <header class="app-header">
    <div class="header-row">
      <div class="brand">
        <img src="__LOGO_DATA_URI__" alt="Endor Labs">
        <div class="brand-copy">
          <h1>Block Mode Readiness Dashboard</h1>
          <p id="header-subtitle">Consolidated warn-to-block snapshot</p>
        </div>
      </div>
      <div class="generated">
        <div id="generated-at">Generated at —</div>
        <span class="snapshot-pill">Static offline snapshot</span>
      </div>
    </div>
  </header>

  <nav class="tabs-shell" aria-label="Dashboard sections">
    <div class="tabs" role="tablist">
      <button class="tab-button active" role="tab" aria-selected="true" aria-controls="tab-overview" data-tab="overview">Overview</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-coverage" data-tab="coverage">Coverage</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-trends" data-tab="trends">Trends</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-developer" data-tab="developer">Developer Behavior</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-findings" data-tab="findings">Findings &amp; False Positives</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-policies" data-tab="policies">Policies</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-checks" data-tab="checks">PR Checks</button>
      <button class="tab-button" role="tab" aria-selected="false" aria-controls="tab-methodology" data-tab="methodology">Methodology</button>
    </div>
  </nav>

  <main>
    <section class="tab-panel" id="tab-overview" role="tabpanel" data-panel="overview">
      <div class="section-heading">
        <h2>Readiness overview</h2>
        <p>Decision metrics from the consolidated tagged-project snapshot.</p>
      </div>
      <div class="kpi-grid" id="overview-kpis"></div>
      <div class="split-grid">
        <div class="card">
          <h3>PR check outcomes</h3>
          <p class="card-subtitle" id="outcome-description"></p>
          <div class="chart-wrap"><canvas id="outcome-chart" aria-label="PR check outcome donut chart"></canvas></div>
        </div>
        <div class="card">
          <h3>Checks with warnings by violation type</h3>
          <p class="card-subtitle">Rates use all PR checks as the denominator.</p>
          <div class="bar-list" id="type-bars"></div>
        </div>
      </div>
      <div class="card">
        <h3>Scope and caveats</h3>
        <ul class="caveats" id="caveat-list"></ul>
      </div>
    </section>

    <section class="tab-panel" id="tab-coverage" role="tabpanel" data-panel="coverage" hidden>
      <div class="section-heading">
        <h2>Repository coverage and concentration</h2>
        <p>Every tagged project is represented, including projects with no checks or no warnings.</p>
      </div>
      <div class="kpi-grid" id="coverage-kpis"></div>
      <div class="card data-table-shell" id="coverage-table"></div>
    </section>

    <section class="tab-panel" id="tab-trends" role="tabpanel" data-panel="trends" hidden>
      <div class="section-heading">
        <h2>PR check trends</h2>
        <p>Calendar-day activity across all snapshots in this consolidated artifact.</p>
      </div>
      <div class="notice"><strong>Snapshot boundary:</strong> the union preserves scan history but not per-collection membership, so this view is a daily timeline rather than a week-over-week snapshot comparison.</div>
      <div class="card">
        <h3>Daily checks, warnings, and blocks</h3>
        <div class="chart-wrap"><canvas id="trend-chart" aria-label="Daily PR checks trend chart"></canvas></div>
      </div>
      <div class="card">
        <h3>Policy mark-date comparisons</h3>
        <div id="mark-splits"></div>
      </div>
    </section>

    <section class="tab-panel" id="tab-developer" role="tabpanel" data-panel="developer" hidden>
      <div class="section-heading">
        <h2>Developer behavior</h2>
        <p>Later Endor scans on the same PR—not GitHub merge behavior.</p>
      </div>
      <div class="kpi-grid" id="developer-kpis"></div>
      <div class="split-grid">
        <div class="card">
          <h3>Trajectory mix</h3>
          <div class="chart-wrap"><canvas id="trajectory-chart" aria-label="Developer trajectory donut chart"></canvas></div>
        </div>
        <div class="card">
          <h3>How classifications work</h3>
          <div class="definition-grid">
            <div class="definition"><h3>Acted</h3><p>A later scan has fewer warnings than the first scan.</p></div>
            <div class="definition"><h3>Cleared</h3><p>The acted subset whose latest scan reached zero warnings.</p></div>
            <div class="definition"><h3>Still open</h3><p>Two or more scans and the latest count did not drop.</p></div>
            <div class="definition"><h3>Single scan</h3><p>Only one scan is available; this is not treated as ignored.</p></div>
          </div>
        </div>
      </div>
      <div class="card data-table-shell" id="trajectory-table"></div>
    </section>

    <section class="tab-panel" id="tab-findings" role="tabpanel" data-panel="findings" hidden>
      <div class="section-heading">
        <h2>Findings and false positives</h2>
        <p>One row per warning finding. Fix availability is an attribute, not remediation status.</p>
      </div>
      <div class="kpi-grid" id="finding-kpis"></div>
      <div class="notice" id="fp-status">False-positive rates require returned labels.</div>
      <div class="card">
        <h3>Warning findings by type and severity</h3>
        <div id="severity-matrix"></div>
      </div>
      <div class="card data-table-shell" id="finding-table"></div>
      <div class="card" id="unmatched-card" hidden>
        <h3>Unmatched label rows</h3>
        <div id="unmatched-labels"></div>
      </div>
    </section>

    <section class="tab-panel" id="tab-policies" role="tabpanel" data-panel="policies" hidden>
      <div class="section-heading">
        <h2>Applicable admission policies</h2>
        <p>Read-only policy context captured with the snapshot.</p>
      </div>
      <div class="notice">Warning-finding counts reflect collected PR warning rows. This artifact does not contain full policy rules, exceptions, or change history.</div>
      <div class="card data-table-shell" id="policy-table"></div>
    </section>

    <section class="tab-panel" id="tab-checks" role="tabpanel" data-panel="checks" hidden>
      <div class="section-heading">
        <h2>PR check denominator</h2>
        <p>Every clean, warn, and block check used to calculate would-have-blocked.</p>
      </div>
      <div class="card data-table-shell" id="check-table"></div>
    </section>

    <section class="tab-panel" id="tab-methodology" role="tabpanel" data-panel="methodology" hidden>
      <div class="section-heading">
        <h2>Methodology and limitations</h2>
        <p>How to read this immutable report artifact.</p>
      </div>
      <div class="definition-grid">
        <div class="definition"><h3>Would-have-blocked</h3><p>Warned PR checks divided by every tagged-project PR check, including clean checks. Existing block outcomes are listed separately.</p></div>
        <div class="definition"><h3>Scope</h3><p>Only CI ScanResults carrying a pr= tag and belonging to projects selected by the supplied project tags are counted.</p></div>
        <div class="definition"><h3>False positives</h3><p>Gate 1 is calculated only from yes/no values returned through fp_worksheet.csv. Yes means false positive; no means true positive.</p></div>
        <div class="definition"><h3>Retention</h3><p>ScanResults remain available through the API for 21 days. Weekly snapshots and union reporting provide durable history.</p></div>
        <div class="definition"><h3>Not merge behavior</h3><p>The report does not call GitHub. It cannot establish merge status, PR comment coverage, CI duration, or whether a warning delayed a merge.</p></div>
        <div class="definition"><h3>Not remediation tracking</h3><p>Finding fix availability and reachability are available, but ticket state, owner, SLA, and verified remediation status are not collected.</p></div>
      </div>
      <p class="footer-note">Prepared by __PREPARED_BY__. Open external PR and Endor links only when network access is available.</p>
    </section>
  </main>

  <script id="dashboard-data" type="application/octet-stream">__DASHBOARD_DATA__</script>
  <script>
  (() => {
    "use strict";

    const encoded = document.getElementById("dashboard-data").textContent.trim();
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
    const DATA = JSON.parse(new TextDecoder().decode(bytes));
    const byId = id => document.getElementById(id);

    const text = value => value === null || value === undefined || value === "" ? "—" : String(value);
    const number = value => Number(value || 0).toLocaleString();
    const percent = value => value === null || value === undefined ? "n/a" : `${Number(value).toFixed(1)}%`;
    const formatDate = value => {
      if (!value) return "—";
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
    };
    const make = (tag, className, content) => {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (content !== undefined) node.textContent = text(content);
      return node;
    };
    const safeUrl = value => {
      if (!value || value === "N/A") return null;
      try {
        const url = new URL(value);
        return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
      } catch (_error) {
        return null;
      }
    };
    const externalLink = (label, url) => {
      const href = safeUrl(url);
      if (!href) return make("span", "", label || "N/A");
      const anchor = make("a", "", label || href);
      anchor.href = href;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      return anchor;
    };
    const statusBadge = (value, tone) => {
      const normalized = String(tone || value || "").toLowerCase().replace(/\s+/g, "_");
      return make("span", `badge badge-${normalized || "empty"}`, value || "unlabeled");
    };
    const rateDetail = (numerator, denominator) => `${number(numerator)} / ${number(denominator)}`;

    function addKpi(root, label, value, detail, tone) {
      const card = make("div", "kpi");
      card.append(
        make("div", "kpi-label", label),
        make("div", `kpi-value ${tone || ""}`, value),
        make("div", "kpi-detail", detail || "")
      );
      root.append(card);
    }

    function renderHeader() {
      const meta = DATA.meta;
      byId("header-subtitle").textContent =
        `${text(meta.namespace)} · ${text(meta.window_start)} – ${text(meta.window_end)} · ${number(meta.snapshot_count)} snapshot${meta.snapshot_count === 1 ? "" : "s"}`;
      byId("generated-at").textContent = `Generated ${formatDate(meta.generated_at)}`;
    }

    function renderOverview() {
      const summary = DATA.summary;
      const root = byId("overview-kpis");
      addKpi(root, "PR checks", number(summary.checks_total), "Denominator", "");
      addKpi(root, "Warned checks", number(summary.checks_warn), rateDetail(summary.checks_warn, summary.checks_total), "warn");
      addKpi(root, "Would-have-blocked", percent(summary.would_have_blocked_pct), rateDetail(summary.checks_warn, summary.checks_total), "warn");
      addKpi(root, "Blocked checks", number(summary.checks_block), "Listed separately", "block");
      addKpi(root, "Tagged projects", number(DATA.meta.project_count), DATA.meta.project_tags.join(", "), "");
      addKpi(root, "Warning findings", number(summary.warning_findings), "Rows to review", "");

      byId("outcome-description").textContent =
        `${number(summary.checks_clean)} clean · ${number(summary.checks_warn)} warn · ${number(summary.checks_block)} block`;
      renderTypeBars();
      const list = byId("caveat-list");
      DATA.caveats.forEach(value => list.append(make("li", "", value)));
    }

    function renderTypeBars() {
      const root = byId("type-bars");
      root.replaceChildren();
      if (!DATA.by_violation_type.length) {
        root.append(make("div", "empty-state", "No warning violation types in this snapshot."));
        return;
      }
      const max = Math.max(...DATA.by_violation_type.map(row => row.checks_with_type), 1);
      DATA.by_violation_type.forEach(row => {
        const wrapper = make("div", "bar-row");
        wrapper.append(make("div", "bar-label", row.violation_type));
        const track = make("div", "bar-track");
        const fill = make("div", "bar-fill");
        fill.style.width = `${Math.max(2, row.checks_with_type / max * 100)}%`;
        track.append(fill);
        wrapper.append(track, make("div", "bar-value", `${number(row.checks_with_type)} · ${percent(row.rate)}`));
        root.append(wrapper);
      });
    }

    function renderCoverage() {
      const root = byId("coverage-kpis");
      const withChecks = DATA.repos.filter(row => row.checks > 0).length;
      addKpi(root, "Projects in scope", number(DATA.repos.length), "Selected by project tags", "");
      addKpi(root, "Projects with checks", number(withChecks), rateDetail(withChecks, DATA.repos.length), "");
      addKpi(root, "Zero-warn projects", number(DATA.summary.zero_warn_repos), rateDetail(DATA.summary.zero_warn_repos, DATA.repos.length), "green");
      addKpi(root, "Top-five warn share", percent(DATA.summary.top_repo_warn_share), "Concentration", "warn");
      mountTable("coverage-table", DATA.repos, [
        {key: "project_name", label: "Repository", render: row => externalLink(row.project_name, row.project_url)},
        {key: "checks", label: "Checks", numeric: true},
        {key: "warns", label: "Warns", numeric: true},
        {key: "rate", label: "Warn rate", numeric: true, format: percent},
        {key: "tags", label: "Tags", value: row => row.tags.join(", ")},
      ], {
        searchPlaceholder: "Search repositories or tags",
        emptyText: "No tagged projects are present in this snapshot.",
        sortKey: "warns",
        sortDirection: "desc",
      });
    }

    function renderTrends() {
      if (!DATA.mark_splits.length) {
        byId("mark-splits").append(make("div", "empty-state", "No policy mark dates were supplied."));
      } else {
        mountTable("mark-splits", DATA.mark_splits, [
          {key: "key", label: "Mark"},
          {key: "date", label: "Date"},
          {key: "before_total", label: "Checks before", numeric: true},
          {key: "before_warn", label: "Warns before", numeric: true},
          {key: "before_rate", label: "Rate before", numeric: true, format: percent},
          {key: "after_total", label: "Checks after", numeric: true},
          {key: "after_warn", label: "Warns after", numeric: true},
          {key: "after_rate", label: "Rate after", numeric: true, format: percent},
        ], {controls: false, pageSize: 25});
      }
    }

    function renderDeveloper() {
      const root = byId("developer-kpis");
      addKpi(root, "Warned PRs", number(DATA.summary.warned_prs), "Trajectory denominator", "");
      addKpi(root, "Acted", number(DATA.summary.acted), "Latest count decreased", "green");
      addKpi(root, "Cleared", number(DATA.summary.cleared), "Subset of acted", "green");
      addKpi(root, "Still open", number(DATA.summary.still_open), "Latest count did not drop", "block");
      addKpi(root, "Single scan", number(DATA.summary.single_scan), "No later scan available", "warn");

      mountTable("trajectory-table", DATA.trajectories, [
        {key: "project_name", label: "Repository"},
        {key: "pr_url", label: "PR", render: row => externalLink(`#${row.pr_number}`, row.pr_url)},
        {key: "first_scan", label: "First scan"},
        {key: "last_scan", label: "Last scan"},
        {key: "scan_count", label: "Scans", numeric: true},
        {key: "sequence", label: "Warning sequence"},
        {key: "classification", label: "Classification", render: row => statusBadge(row.classification)},
        {key: "first_scan_result_url", label: "Endor", render: row => externalLink("First", row.first_scan_result_url)},
        {key: "last_scan_result_url", label: "Latest", render: row => externalLink("Latest", row.last_scan_result_url)},
      ], {
        filters: [{key: "classification", label: "Classification"}],
        searchPlaceholder: "Search repository, PR, or sequence",
        emptyText: "No warned PR trajectories are available.",
      });
    }

    function renderFindings() {
      const fp = DATA.false_positives;
      const root = byId("finding-kpis");
      const labeled = fp.per_finding_counts ? fp.per_finding_counts[1] : 0;
      addKpi(root, "Warning findings", number(DATA.findings.length), "Worksheet rows", "");
      addKpi(root, "Labeled findings", number(labeled), rateDetail(labeled, DATA.findings.length), "");
      addKpi(root, "FP rate per finding", fp.available ? percent(fp.per_finding_rate) : "Awaiting labels", fp.per_finding_counts ? rateDetail(fp.per_finding_counts[0], fp.per_finding_counts[1]) : "", fp.available ? "warn" : "");
      addKpi(root, "FP rate per PR", fp.available ? percent(fp.per_pr_rate) : "Awaiting labels", fp.per_pr_counts ? rateDetail(fp.per_pr_counts[0], fp.per_pr_counts[1]) : "", fp.available ? "warn" : "");

      const status = byId("fp-status");
      status.textContent = fp.available
        ? `Gate 1 uses ${number(labeled)} yes/no labeled finding rows. Yes means false positive; no means true positive.`
        : "False-positive rates require returned labels. Complete fp and reason in fp_worksheet.csv, then regenerate with --labels.";
      renderSeverityMatrix();

      mountTable("finding-table", DATA.findings, [
        {key: "date", label: "Date"},
        {key: "project_name", label: "Repository"},
        {key: "violation_type", label: "Type"},
        {key: "policy", label: "Policy"},
        {key: "severity", label: "Severity", render: row => statusBadge(row.severity)},
        {key: "finding", label: "Finding"},
        {key: "package", label: "Package"},
        {key: "reachable", label: "Reachability"},
        {key: "fix_available", label: "Fix available"},
        {key: "fp", label: "FP", render: row => statusBadge(row.fp)},
        {key: "reason", label: "Reason"},
        {key: "pr_url", label: "PR", render: row => externalLink("PR", row.pr_url)},
        {key: "scan_result_url", label: "Scan", render: row => externalLink("Scan", row.scan_result_url)},
        {key: "finding_url", label: "Endor", render: row => externalLink("Finding", row.finding_url)},
      ], {
        filters: [
          {key: "violation_type", label: "Violation type"},
          {key: "severity", label: "Severity"},
          {key: "fp", label: "FP label"},
        ],
        searchPlaceholder: "Search findings, repositories, packages, or policies",
        emptyText: "No warning findings are present in this snapshot.",
        pageSize: 25,
      });

      if (fp.unmatched_labels.length) {
        byId("unmatched-card").hidden = false;
        mountTable("unmatched-labels", fp.unmatched_labels, [
          {key: "finding_uuid", label: "Finding UUID"},
          {key: "scan_result_uuid", label: "Scan UUID"},
          {key: "fp", label: "FP"},
          {key: "reason", label: "Reason"},
        ], {controls: false});
      }
    }

    function renderSeverityMatrix() {
      const severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
      const rows = Object.entries(DATA.finding_counts_by_type_severity).map(([type, counts]) => ({
        type,
        ...Object.fromEntries(severities.map(severity => [severity, counts[severity] || 0])),
        total: Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0),
      }));
      mountTable("severity-matrix", rows, [
        {key: "type", label: "Violation type"},
        ...severities.map(key => ({key, label: key, numeric: true})),
        {key: "total", label: "Total", numeric: true},
      ], {
        controls: false,
        emptyText: "No warning findings are present in this snapshot.",
      });
    }

    function renderPolicies() {
      mountTable("policy-table", DATA.policies, [
        {key: "name", label: "Policy"},
        {key: "uuid", label: "UUID"},
        {key: "selector_tags", label: "Selector tags", value: row => row.selector_tags.join(", ")},
        {key: "state", label: "State", render: row => statusBadge(row.state, row.disabled ? "block" : "clean")},
        {key: "warning_findings", label: "Warning findings", numeric: true},
      ], {
        searchPlaceholder: "Search policies or selector tags",
        emptyText: "No applicable admission policies were captured.",
      });
    }

    function renderChecks() {
      mountTable("check-table", DATA.pr_checks, [
        {key: "date", label: "Date"},
        {key: "project_name", label: "Repository"},
        {key: "pr_url", label: "PR", render: row => externalLink(`#${row.pr_number}`, row.pr_url)},
        {key: "outcome", label: "Outcome", render: row => statusBadge(row.outcome)},
        {key: "warning_findings", label: "Warnings", numeric: true},
        {key: "blocking_findings", label: "Blocks", numeric: true},
        {key: "violation_types", label: "Violation types"},
        {key: "status", label: "Scan status"},
        {key: "project_url", label: "Project", render: row => externalLink("Endor project", row.project_url)},
        {key: "scan_result_url", label: "Scan", render: row => externalLink("Scan result", row.scan_result_url)},
      ], {
        filters: [
          {key: "outcome", label: "Outcome"},
          {key: "violation_types", label: "Violation type"},
          {key: "status", label: "Scan status"},
        ],
        searchPlaceholder: "Search checks, repositories, PRs, or violation types",
        emptyText: "No PR checks match this snapshot.",
        pageSize: 50,
      });
    }

    function mountTable(rootId, sourceRows, columns, config = {}) {
      const root = byId(rootId);
      root.replaceChildren();
      const rows = Array.isArray(sourceRows) ? sourceRows : [];
      const state = {
        search: "",
        filters: {},
        page: 1,
        pageSize: config.pageSize || 25,
        sortKey: config.sortKey || "",
        sortDirection: config.sortDirection || "asc",
      };

      const valueFor = (row, column) => column.value ? column.value(row) : row[column.key];
      let body;
      let footerLabel;
      let previous;
      let next;

      if (config.controls !== false) {
        const controls = make("div", "table-controls");
        const search = document.createElement("input");
        search.type = "search";
        search.placeholder = config.searchPlaceholder || "Search";
        search.setAttribute("aria-label", search.placeholder);
        search.addEventListener("input", () => {
          state.search = search.value.trim().toLowerCase();
          state.page = 1;
          update();
        });
        controls.append(search);

        (config.filters || []).forEach(filter => {
          const select = document.createElement("select");
          select.setAttribute("aria-label", `Filter by ${filter.label}`);
          const all = make("option", "", `All ${filter.label.toLowerCase()}`);
          all.value = "";
          select.append(all);
          const values = [...new Set(rows.map(row => text(row[filter.key])).filter(value => value !== "—"))].sort();
          values.forEach(value => {
            const option = make("option", "", value);
            option.value = value;
            select.append(option);
          });
          select.addEventListener("change", () => {
            state.filters[filter.key] = select.value;
            state.page = 1;
            update();
          });
          controls.append(select);
        });
        root.append(controls);
      }

      const scroller = make("div", "table-scroller");
      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headerRow = document.createElement("tr");
      columns.forEach(column => {
        const th = document.createElement("th");
        const button = make("button", "", column.label);
        button.type = "button";
        button.addEventListener("click", () => {
          if (state.sortKey === column.key) {
            state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
          } else {
            state.sortKey = column.key;
            state.sortDirection = column.numeric ? "desc" : "asc";
          }
          update();
        });
        th.append(button);
        headerRow.append(th);
      });
      head.append(headerRow);
      body = document.createElement("tbody");
      table.append(head, body);
      scroller.append(table);
      root.append(scroller);

      const footer = make("div", "table-footer");
      footerLabel = make("span", "", "");
      const pager = make("div", "pager");
      previous = make("button", "", "Previous");
      next = make("button", "", "Next");
      previous.type = next.type = "button";
      previous.addEventListener("click", () => {
        state.page = Math.max(1, state.page - 1);
        update();
      });
      next.addEventListener("click", () => {
        state.page += 1;
        update();
      });
      pager.append(previous, next);
      footer.append(footerLabel, pager);
      root.append(footer);

      function filteredRows() {
        let output = rows.filter(row => {
          const filterMatch = Object.entries(state.filters).every(([key, value]) =>
            !value || text(row[key]) === value
          );
          if (!filterMatch) return false;
          if (!state.search) return true;
          return columns.some(column =>
            text(valueFor(row, column)).toLowerCase().includes(state.search)
          );
        });
        if (state.sortKey) {
          const column = columns.find(candidate => candidate.key === state.sortKey);
          if (column) {
            output = [...output].sort((left, right) => {
              const a = valueFor(left, column);
              const b = valueFor(right, column);
              if (column.numeric) return (Number(a) || 0) - (Number(b) || 0);
              return text(a).localeCompare(text(b), undefined, {numeric: true, sensitivity: "base"});
            });
            if (state.sortDirection === "desc") output.reverse();
          }
        }
        return output;
      }

      function update() {
        const filtered = filteredRows();
        const pageCount = Math.max(1, Math.ceil(filtered.length / state.pageSize));
        state.page = Math.min(state.page, pageCount);
        const start = (state.page - 1) * state.pageSize;
        const pageRows = filtered.slice(start, start + state.pageSize);
        body.replaceChildren();

        if (!pageRows.length) {
          const row = document.createElement("tr");
          const cell = make("td", "empty-state", config.emptyText || "No rows match the current filters.");
          cell.colSpan = columns.length;
          row.append(cell);
          body.append(row);
        } else {
          pageRows.forEach(rowData => {
            const row = document.createElement("tr");
            columns.forEach(column => {
              const cell = document.createElement("td");
              if (column.render) {
                cell.append(column.render(rowData));
              } else {
                const raw = valueFor(rowData, column);
                cell.textContent = column.format ? column.format(raw) : text(raw);
              }
              row.append(cell);
            });
            body.append(row);
          });
        }
        const end = Math.min(start + state.pageSize, filtered.length);
        footerLabel.textContent = filtered.length
          ? `${number(start + 1)}–${number(end)} of ${number(filtered.length)}`
          : `0 of ${number(rows.length)}`;
        previous.disabled = state.page <= 1;
        next.disabled = state.page >= pageCount;
      }
      update();
    }

    function setupTabs() {
      const buttons = [...document.querySelectorAll(".tab-button")];
      const panels = [...document.querySelectorAll(".tab-panel")];
      const activate = name => {
        const validName = panels.some(panel => panel.dataset.panel === name) ? name : "overview";
        buttons.forEach(button => {
          const active = button.dataset.tab === validName;
          button.classList.toggle("active", active);
          button.setAttribute("aria-selected", String(active));
        });
        panels.forEach(panel => {
          panel.hidden = panel.dataset.panel !== validName;
        });
        if (location.hash !== `#${validName}`) history.replaceState(null, "", `#${validName}`);
        requestAnimationFrame(renderCharts);
      };
      buttons.forEach(button => button.addEventListener("click", () => activate(button.dataset.tab)));
      activate(location.hash.slice(1) || "overview");
    }

    function setupCanvas(canvas) {
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(canvas.parentElement.clientWidth || 700, 300);
      const height = 260;
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const context = canvas.getContext("2d");
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      return {context, width, height};
    }

    function drawDonut(canvas, slices, centerText) {
      const {context, width, height} = setupCanvas(canvas);
      const total = slices.reduce((sum, slice) => sum + slice.value, 0);
      const centerX = width / 2;
      const centerY = height / 2 - 4;
      const radius = Math.min(width, height) * 0.31;
      const thickness = Math.max(18, radius * 0.32);
      context.lineWidth = thickness;
      context.lineCap = "butt";
      if (!total) {
        context.strokeStyle = "#e7eaf0";
        context.beginPath();
        context.arc(centerX, centerY, radius, 0, Math.PI * 2);
        context.stroke();
      } else {
        let angle = -Math.PI / 2;
        slices.forEach(slice => {
          if (!slice.value) return;
          const next = angle + slice.value / total * Math.PI * 2;
          context.strokeStyle = slice.color;
          context.beginPath();
          context.arc(centerX, centerY, radius, angle, next);
          context.stroke();
          angle = next;
        });
      }
      context.textAlign = "center";
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--text");
      context.font = "700 24px Inter, sans-serif";
      context.fillText(centerText, centerX, centerY + 5);
      context.font = "12px Inter, sans-serif";
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--secondary");
      context.fillText(`${number(total)} total`, centerX, centerY + 26);

      let legendX = 16;
      const legendY = height - 12;
      context.textAlign = "left";
      context.font = "11px Inter, sans-serif";
      slices.forEach(slice => {
        context.fillStyle = slice.color;
        context.fillRect(legendX, legendY - 8, 10, 10);
        context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--secondary");
        const label = `${slice.label} (${number(slice.value)})`;
        context.fillText(label, legendX + 15, legendY);
        legendX += context.measureText(label).width + 38;
      });
    }

    function drawTrend(canvas, rows) {
      const {context, width, height} = setupCanvas(canvas);
      const padding = {left: 42, right: 18, top: 18, bottom: 38};
      const plotWidth = width - padding.left - padding.right;
      const plotHeight = height - padding.top - padding.bottom;
      const max = Math.max(1, ...rows.flatMap(row => [row.checks, row.warn, row.block]));
      context.strokeStyle = "#e2e6eb";
      context.fillStyle = "#6a7483";
      context.font = "10px Inter, sans-serif";
      context.textAlign = "right";
      for (let index = 0; index <= 4; index += 1) {
        const value = Math.round(max * index / 4);
        const y = padding.top + plotHeight - plotHeight * index / 4;
        context.beginPath();
        context.moveTo(padding.left, y);
        context.lineTo(width - padding.right, y);
        context.stroke();
        context.fillText(number(value), padding.left - 7, y + 3);
      }
      if (!rows.length) {
        context.textAlign = "center";
        context.fillText("No PR check trend data.", width / 2, height / 2);
        return;
      }
      const x = index => rows.length === 1
        ? padding.left + plotWidth / 2
        : padding.left + plotWidth * index / (rows.length - 1);
      const y = value => padding.top + plotHeight - Number(value || 0) / max * plotHeight;
      const series = [
        {key: "checks", color: "#3D6B8E", label: "Checks"},
        {key: "warn", color: "__BRAND_WARN__", label: "Warns"},
        {key: "block", color: "__BRAND_BLOCK__", label: "Blocks"},
      ];
      series.forEach(line => {
        context.strokeStyle = line.color;
        context.lineWidth = line.key === "checks" ? 2.5 : 2;
        context.beginPath();
        rows.forEach((row, index) => {
          const command = index === 0 ? "moveTo" : "lineTo";
          context[command](x(index), y(row[line.key]));
        });
        context.stroke();
      });
      const labelIndexes = new Set([0, rows.length - 1, Math.floor((rows.length - 1) / 2)]);
      context.fillStyle = "#6a7483";
      context.textAlign = "center";
      [...labelIndexes].forEach(index => {
        context.fillText(rows[index].date.slice(5), x(index), height - 17);
      });
      let legendX = padding.left;
      series.forEach(line => {
        context.fillStyle = line.color;
        context.fillRect(legendX, 3, 11, 3);
        context.fillStyle = "#5A6577";
        context.textAlign = "left";
        context.fillText(line.label, legendX + 16, 8);
        legendX += 72;
      });
    }

    function renderCharts() {
      drawDonut(byId("outcome-chart"), [
        {label: "Clean", value: DATA.summary.checks_clean, color: "__BRAND_GREEN__"},
        {label: "Warn", value: DATA.summary.checks_warn, color: "__BRAND_WARN__"},
        {label: "Block", value: DATA.summary.checks_block, color: "__BRAND_BLOCK__"},
      ], percent(DATA.summary.would_have_blocked_pct));
      drawDonut(byId("trajectory-chart"), [
        {label: "Acted", value: DATA.summary.acted, color: "__BRAND_GREEN__"},
        {label: "Still open", value: DATA.summary.still_open, color: "__BRAND_BLOCK__"},
        {label: "Single scan", value: DATA.summary.single_scan, color: "__BRAND_WARN__"},
      ], number(DATA.summary.warned_prs));
      drawTrend(byId("trend-chart"), DATA.daily);
    }

    renderHeader();
    renderOverview();
    renderCoverage();
    renderTrends();
    renderDeveloper();
    renderFindings();
    renderPolicies();
    renderChecks();
    setupTabs();
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderCharts, 100);
    });
  })();
  </script>
</body>
</html>
"""
