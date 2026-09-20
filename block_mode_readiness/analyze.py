from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from classify import classify_trajectory, is_cleared
from snapshot import UI_BASE, Finding, Scan, Snapshot


@dataclass
class TypeStats:
    violation_type: str
    checks_with_type: int
    rate: Optional[float]


@dataclass
class MarkSplit:
    key: str
    date: str
    before_total: int
    before_warn: int
    before_block: int
    after_total: int
    after_warn: int
    after_block: int


@dataclass
class RepoRow:
    project_uuid: str
    project_name: str
    checks: int
    warns: int
    rate: Optional[float]


@dataclass
class Trajectory:
    project_name: str
    pr_url: str
    first_scan: str
    last_scan: str
    scan_count: int
    first_warning_count: int
    last_warning_count: int
    sequence: str
    classification: str
    first_scan_result_url: str
    last_scan_result_url: str
    project_uuid: str
    pr_number: str


@dataclass
class Analysis:
    window_start: str
    window_end: str
    checks_total: int
    checks_warn: int
    checks_block: int
    would_have_blocked_pct: Optional[float]
    by_violation_type: List[TypeStats]
    mark_splits: List[MarkSplit]
    repos: List[RepoRow]
    d_acted: int
    d_still_open: int
    d_single_scan: int
    d_cleared: int
    d_warned_prs: int
    trajectories: List[Trajectory]
    pr_check_rows: List[Dict[str, Any]]
    fp_rows: List[Dict[str, Any]]
    unmatched_labels: List[Dict[str, str]]
    gate1_per_finding: Optional[float]
    gate1_per_finding_counts: Optional[Tuple[int, int]]
    gate1_per_pr: Optional[float]
    gate1_per_pr_counts: Optional[Tuple[int, int]]
    gate1_by_type: Optional[Dict[str, Optional[float]]]
    gate1_by_type_counts: Optional[Dict[str, Tuple[int, int]]]
    gate1_by_type_per_pr: Optional[Dict[str, Optional[float]]]
    gate1_by_type_per_pr_counts: Optional[Dict[str, Tuple[int, int]]]
    snapshot_count: int
    history_starts_at: str
    policy_fallback: bool
    zero_warn_repos: int
    top_repo_warn_share: Optional[float]
    finding_counts_by_type_severity: Dict[str, Dict[str, int]]


def pct(n: int, d: int) -> Optional[float]:
    if d == 0:
        return None
    return round(100.0 * n / d, 1)


def build_pr_url(base_url: str, pr_number: Optional[str]) -> str:
    if not base_url or not pr_number:
        return "N/A"
    return f"{base_url}/pull/{pr_number}"


def scan_url(namespace: str, uuid: str) -> str:
    return f"{UI_BASE}/t/{namespace}/scan-history/{uuid}"


def finding_url(namespace: str, uuid: str) -> str:
    return f"{UI_BASE}/t/{namespace}/findings/{uuid}"


def project_url(namespace: str, uuid: str) -> str:
    return f"{UI_BASE}/t/{namespace}/projects/{uuid}"


def _parse_create_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _scan_date(scan: Scan) -> str:
    return scan.create_time[:10]


def _warning_findings(scan: Scan, findings: Dict[str, Finding]) -> List[Finding]:
    out: List[Finding] = []
    for finding_id in scan.warning_finding_ids:
        finding = findings.get(finding_id)
        if finding is not None:
            out.append(finding)
    return out


def _warning_types(scan: Scan, findings: Dict[str, Finding]) -> List[str]:
    types = {finding.violation_type for finding in _warning_findings(scan, findings)}
    return sorted(types)


def _policy_for_finding(scan: Scan, violation_type: str) -> Tuple[str, bool]:
    policy = (scan.policy_name or "").strip()
    if policy:
        return policy, False
    return violation_type, True


def analyze(
    snapshot: Snapshot,
    labels: Optional[List[Dict[str, str]]] = None,
    snapshot_count: int = 1,
) -> Analysis:
    scans = list(snapshot.scans.values())
    findings = snapshot.findings

    parsed_times = [_parse_create_time(scan.create_time) for scan in scans]
    if parsed_times:
        window_start = min(parsed_times).date().isoformat()
        window_end = max(parsed_times).date().isoformat()
    else:
        window_start = ""
        window_end = ""

    checks_total = len(scans)
    checks_warn = sum(1 for scan in scans if scan.outcome == "warn")
    checks_block = sum(1 for scan in scans if scan.outcome == "block")

    type_counts: Dict[str, int] = defaultdict(int)
    for scan in scans:
        for vtype in _warning_types(scan, findings):
            type_counts[vtype] += 1
    by_violation_type = [
        TypeStats(
            violation_type=vtype,
            checks_with_type=count,
            rate=pct(count, checks_total),
        )
        for vtype, count in sorted(type_counts.items())
    ]

    mark_splits: List[MarkSplit] = []
    for key, date in snapshot.meta.mark_dates.items():
        before_total = 0
        before_warn = 0
        before_block = 0
        after_total = 0
        after_warn = 0
        after_block = 0
        for scan in scans:
            if _scan_date(scan) < date:
                before_total += 1
                if scan.outcome == "warn":
                    before_warn += 1
                elif scan.outcome == "block":
                    before_block += 1
            else:
                after_total += 1
                if scan.outcome == "warn":
                    after_warn += 1
                elif scan.outcome == "block":
                    after_block += 1
        mark_splits.append(
            MarkSplit(
                key=key,
                date=date,
                before_total=before_total,
                before_warn=before_warn,
                before_block=before_block,
                after_total=after_total,
                after_warn=after_warn,
                after_block=after_block,
            )
        )

    checks_by_project: Dict[str, int] = defaultdict(int)
    warns_by_project: Dict[str, int] = defaultdict(int)
    for scan in scans:
        checks_by_project[scan.project_uuid] += 1
        if scan.outcome == "warn":
            warns_by_project[scan.project_uuid] += 1

    repos: List[RepoRow] = []
    for project in snapshot.projects.values():
        checks = checks_by_project.get(project.uuid, 0)
        warns = warns_by_project.get(project.uuid, 0)
        repos.append(
            RepoRow(
                project_uuid=project.uuid,
                project_name=project.full_name,
                checks=checks,
                warns=warns,
                rate=pct(warns, checks),
            )
        )
    repos.sort(key=lambda row: (-row.warns, row.project_name))

    total_warns = sum(row.warns for row in repos)
    top_n = min(5, len(repos))
    top_repo_warn_share = pct(sum(row.warns for row in repos[:top_n]), total_warns)
    zero_warn_repos = sum(1 for row in repos if row.warns == 0)

    groups: Dict[Tuple[str, str], List[Scan]] = defaultdict(list)
    for scan in scans:
        if not scan.pr_number:
            continue
        groups[(scan.project_uuid, scan.pr_number)].append(scan)

    trajectories: List[Trajectory] = []
    d_acted = 0
    d_still_open = 0
    d_single_scan = 0
    d_cleared = 0
    for (project_uuid, pr_number), group in groups.items():
        group.sort(key=lambda scan: _parse_create_time(scan.create_time))
        warned = any(
            scan.outcome == "warn" or len(scan.warning_finding_ids) > 0
            for scan in group
        )
        if not warned:
            continue
        counts = [len(scan.warning_finding_ids) for scan in group]
        scan_count = len(group)
        first_warning_count = counts[0]
        last_warning_count = counts[-1]
        classification = classify_trajectory(
            scan_count, first_warning_count, last_warning_count
        )
        if classification == "acted":
            d_acted += 1
        elif classification == "still_open":
            d_still_open += 1
        elif classification == "single_scan":
            d_single_scan += 1
        if is_cleared(last_warning_count, classification):
            d_cleared += 1
        project = snapshot.projects.get(project_uuid)
        project_name = project.full_name if project else ""
        base_url = project.base_url if project else ""
        namespace = group[0].namespace or (project.namespace if project else "")
        first_scan = group[0]
        last_scan = group[-1]
        trajectories.append(
            Trajectory(
                project_name=project_name,
                pr_url=build_pr_url(base_url, pr_number),
                first_scan=_scan_date(first_scan),
                last_scan=_scan_date(last_scan),
                scan_count=scan_count,
                first_warning_count=first_warning_count,
                last_warning_count=last_warning_count,
                sequence="→".join(str(count) for count in counts),
                classification=classification,
                first_scan_result_url=scan_url(namespace, first_scan.uuid),
                last_scan_result_url=scan_url(namespace, last_scan.uuid),
                project_uuid=project_uuid,
                pr_number=pr_number,
            )
        )
    trajectories.sort(key=lambda row: (row.project_name, row.pr_number))

    pr_check_rows: List[Dict[str, Any]] = []
    for scan in sorted(scans, key=lambda item: _parse_create_time(item.create_time)):
        project = snapshot.projects.get(scan.project_uuid)
        project_name = project.full_name if project else ""
        base_url = project.base_url if project else ""
        namespace = scan.namespace or (project.namespace if project else "")
        pr_check_rows.append(
            {
                "date": _scan_date(scan),
                "project_name": project_name,
                "project_uuid": scan.project_uuid,
                "project_url": project_url(namespace, scan.project_uuid),
                "pr_number": scan.pr_number or "",
                "pr_url": build_pr_url(base_url, scan.pr_number),
                "scan_result_url": scan_url(namespace, scan.uuid),
                "outcome": scan.outcome,
                "warning_findings": len(scan.warning_finding_ids),
                "blocking_findings": len(scan.blocking_finding_ids),
                "violation_types": "|".join(_warning_types(scan, findings)),
                "status": scan.status,
            }
        )

    fp_rows: List[Dict[str, Any]] = []
    policy_fallback = False
    finding_counts_by_type_severity: Dict[str, Dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for scan in sorted(scans, key=lambda item: _parse_create_time(item.create_time)):
        if scan.outcome != "warn" and not scan.warning_finding_ids:
            continue
        project = snapshot.projects.get(scan.project_uuid)
        project_name = project.full_name if project else ""
        base_url = project.base_url if project else ""
        namespace = scan.namespace or (project.namespace if project else "")
        for finding in _warning_findings(scan, findings):
            policy, used_fallback = _policy_for_finding(scan, finding.violation_type)
            if used_fallback:
                policy_fallback = True
            fp_rows.append(
                {
                    "date": _scan_date(scan),
                    "project_name": project_name,
                    "pr_url": build_pr_url(base_url, scan.pr_number),
                    "scan_result_url": scan_url(namespace, scan.uuid),
                    "finding_url": finding_url(finding.namespace or namespace, finding.uuid),
                    "violation_type": finding.violation_type,
                    "policy": policy,
                    "severity": finding.severity,
                    "finding": finding.description,
                    "vuln_id": finding.vuln_id,
                    "rule_id": finding.rule_id,
                    "package": finding.package,
                    "reachable": finding.reachable,
                    "fix_available": finding.fix_available,
                    "fp": "",
                    "reason": "",
                    "finding_uuid": finding.uuid,
                    "scan_result_uuid": scan.uuid,
                    "project_uuid": scan.project_uuid,
                }
            )
            finding_counts_by_type_severity[finding.violation_type][
                finding.severity
            ] += 1

    unmatched_labels: List[Dict[str, str]] = []
    gate1_per_finding: Optional[float] = None
    gate1_per_finding_counts: Optional[Tuple[int, int]] = None
    gate1_per_pr: Optional[float] = None
    gate1_per_pr_counts: Optional[Tuple[int, int]] = None
    gate1_by_type: Optional[Dict[str, Optional[float]]] = None
    gate1_by_type_counts: Optional[Dict[str, Tuple[int, int]]] = None
    gate1_by_type_per_pr: Optional[Dict[str, Optional[float]]] = None
    gate1_by_type_per_pr_counts: Optional[Dict[str, Tuple[int, int]]] = None
    if labels is not None:
        fp_index = {
            (row["finding_uuid"], row["scan_result_uuid"]): row for row in fp_rows
        }
        for label in labels:
            key = (label["finding_uuid"], label["scan_result_uuid"])
            row = fp_index.get(key)
            if row is None:
                unmatched_labels.append(label)
                continue
            row["fp"] = label.get("fp", "")
            row["reason"] = label.get("reason", "")

        yes_no: List[Tuple[str, Dict[str, Any]]] = []
        for row in fp_rows:
            fp_val = str(row.get("fp", "")).strip().lower()
            if fp_val in ("yes", "no"):
                yes_no.append((fp_val, row))

        yes_count = sum(1 for fp_val, _ in yes_no if fp_val == "yes")
        gate1_per_finding = pct(yes_count, len(yes_no))
        gate1_per_finding_counts = (yes_count, len(yes_no))

        pr_groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        type_yes: Dict[str, int] = defaultdict(int)
        type_total: Dict[str, int] = defaultdict(int)
        type_pr_groups: Dict[
            str, Dict[Tuple[str, str], List[str]]
        ] = defaultdict(lambda: defaultdict(list))
        for fp_val, row in yes_no:
            pr_key = (row["project_uuid"], row["pr_url"])
            pr_groups[pr_key].append(fp_val)
            vtype = row["violation_type"]
            type_total[vtype] += 1
            type_pr_groups[vtype][pr_key].append(fp_val)
            if fp_val == "yes":
                type_yes[vtype] += 1

        fp_prs = 0
        tp_prs = 0
        for values in pr_groups.values():
            if all(value == "yes" for value in values):
                fp_prs += 1
            elif any(value == "no" for value in values):
                tp_prs += 1
        gate1_per_pr = pct(fp_prs, fp_prs + tp_prs)
        gate1_per_pr_counts = (fp_prs, fp_prs + tp_prs)
        gate1_by_type = {
            vtype: pct(type_yes[vtype], type_total[vtype])
            for vtype in sorted(type_total)
        }
        gate1_by_type_counts = {
            vtype: (type_yes[vtype], type_total[vtype])
            for vtype in sorted(type_total)
        }
        gate1_by_type_per_pr = {}
        gate1_by_type_per_pr_counts = {}
        for vtype in sorted(type_pr_groups):
            type_fp_prs = sum(
                1
                for values in type_pr_groups[vtype].values()
                if all(value == "yes" for value in values)
            )
            type_labeled_prs = len(type_pr_groups[vtype])
            gate1_by_type_per_pr[vtype] = pct(
                type_fp_prs,
                type_labeled_prs,
            )
            gate1_by_type_per_pr_counts[vtype] = (
                type_fp_prs,
                type_labeled_prs,
            )

    return Analysis(
        window_start=window_start,
        window_end=window_end,
        checks_total=checks_total,
        checks_warn=checks_warn,
        checks_block=checks_block,
        would_have_blocked_pct=pct(checks_warn, checks_total),
        by_violation_type=by_violation_type,
        mark_splits=mark_splits,
        repos=repos,
        d_acted=d_acted,
        d_still_open=d_still_open,
        d_single_scan=d_single_scan,
        d_cleared=d_cleared,
        d_warned_prs=len(trajectories),
        trajectories=trajectories,
        pr_check_rows=pr_check_rows,
        fp_rows=fp_rows,
        unmatched_labels=unmatched_labels,
        gate1_per_finding=gate1_per_finding,
        gate1_per_finding_counts=gate1_per_finding_counts,
        gate1_per_pr=gate1_per_pr,
        gate1_per_pr_counts=gate1_per_pr_counts,
        gate1_by_type=gate1_by_type,
        gate1_by_type_counts=gate1_by_type_counts,
        gate1_by_type_per_pr=gate1_by_type_per_pr,
        gate1_by_type_per_pr_counts=gate1_by_type_per_pr_counts,
        snapshot_count=snapshot_count,
        history_starts_at=window_start,
        policy_fallback=policy_fallback,
        zero_warn_repos=zero_warn_repos,
        top_repo_warn_share=top_repo_warn_share,
        finding_counts_by_type_severity={
            vtype: dict(severities)
            for vtype, severities in finding_counts_by_type_severity.items()
        },
    )
