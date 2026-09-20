from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from analyze import Analysis
from snapshot import Snapshot

PR_CHECK_FIELDS = [
    "date",
    "project_name",
    "project_uuid",
    "project_url",
    "pr_number",
    "pr_url",
    "scan_result_url",
    "outcome",
    "warning_findings",
    "blocking_findings",
    "violation_types",
    "status",
]

FP_FIELDS = [
    "date",
    "project_name",
    "pr_url",
    "scan_result_url",
    "finding_url",
    "violation_type",
    "policy",
    "severity",
    "finding",
    "vuln_id",
    "rule_id",
    "package",
    "reachable",
    "fix_available",
    "fp",
    "reason",
    "finding_uuid",
    "scan_result_uuid",
    "project_uuid",
]

TRAJECTORY_FIELDS = [
    "project_name",
    "pr_url",
    "first_scan",
    "last_scan",
    "scan_count",
    "first_warning_count",
    "last_warning_count",
    "sequence",
    "classification",
    "first_scan_result_url",
    "last_scan_result_url",
]


def _write_csv(path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_csvs(analysis: Analysis, directory: Path) -> None:
    _write_csv(directory / "pr_checks.csv", PR_CHECK_FIELDS, analysis.pr_check_rows)
    _write_csv(directory / "fp_worksheet.csv", FP_FIELDS, analysis.fp_rows)
    trajectories = [
        {field: asdict(traj)[field] for field in TRAJECTORY_FIELDS}
        for traj in analysis.trajectories
    ]
    _write_csv(directory / "pr_trajectories.csv", TRAJECTORY_FIELDS, trajectories)


def write_summary(analysis: Analysis, snapshot: Snapshot, directory: Path) -> None:
    data = {
        "namespace": snapshot.meta.namespace,
        "project_tags": snapshot.meta.project_tags,
        "days": snapshot.meta.days,
        "mark_dates": snapshot.meta.mark_dates,
        "customer": snapshot.meta.customer,
        "decision_date": snapshot.meta.decision_date,
        "generated_at": snapshot.meta.generated_at,
        "ci_runs_dropped_no_pr": snapshot.meta.ci_runs_dropped_no_pr,
        "project_count": snapshot.meta.project_count,
        "window_start": analysis.window_start,
        "window_end": analysis.window_end,
        "history_starts_at": analysis.history_starts_at,
        "snapshot_count": analysis.snapshot_count,
        "checks_total": analysis.checks_total,
        "checks_warn": analysis.checks_warn,
        "checks_block": analysis.checks_block,
        "would_have_blocked_pct": analysis.would_have_blocked_pct,
        "d_acted": analysis.d_acted,
        "d_still_open": analysis.d_still_open,
        "d_single_scan": analysis.d_single_scan,
        "d_cleared": analysis.d_cleared,
        "d_warned_prs": analysis.d_warned_prs,
        "zero_warn_repos": analysis.zero_warn_repos,
        "top_repo_warn_share": analysis.top_repo_warn_share,
        "policy_fallback": analysis.policy_fallback,
        "gate1_per_finding": analysis.gate1_per_finding,
        "gate1_per_pr": analysis.gate1_per_pr,
        "gate1_by_type": analysis.gate1_by_type,
        "unmatched_labels": analysis.unmatched_labels,
        "by_violation_type": [asdict(item) for item in analysis.by_violation_type],
        "mark_splits": [asdict(item) for item in analysis.mark_splits],
        "finding_counts_by_type_severity": analysis.finding_counts_by_type_severity,
    }
    (directory / "summary.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_labels_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
