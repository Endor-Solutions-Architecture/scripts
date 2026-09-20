from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

UI_BASE = "https://app.endorlabs.com"


@dataclass
class Project:
    uuid: str
    full_name: str
    base_url: str
    namespace: str
    tags: List[str]


@dataclass
class Finding:
    uuid: str
    violation_type: str
    severity: str
    description: str
    vuln_id: str
    rule_id: str
    package: str
    reachable: str
    fix_available: str
    namespace: str


@dataclass
class Scan:
    uuid: str
    create_time: str
    project_uuid: str
    pr_number: Optional[str]
    outcome: str
    warning_finding_ids: List[str]
    blocking_finding_ids: List[str]
    status: str
    namespace: str
    policy_name: str


@dataclass
class Policy:
    uuid: str
    name: str
    selector_tags: List[str]
    disabled: bool


@dataclass
class SnapshotMeta:
    namespace: str
    project_tags: List[str]
    days: int
    mark_dates: Dict[str, str]
    customer: str
    decision_date: Optional[str]
    generated_at: str
    ci_runs_dropped_no_pr: int
    project_count: int


@dataclass
class Snapshot:
    meta: SnapshotMeta
    projects: Dict[str, Project]
    scans: Dict[str, Scan]
    findings: Dict[str, Finding]
    policies: List[Policy]


class SnapshotError(Exception):
    pass


def _project_from_dict(data: dict) -> Project:
    return Project(**data)


def _finding_from_dict(data: dict) -> Finding:
    return Finding(**data)


def _scan_from_dict(data: dict) -> Scan:
    return Scan(**data)


def _policy_from_dict(data: dict) -> Policy:
    return Policy(**data)


def _meta_from_dict(data: dict) -> SnapshotMeta:
    return SnapshotMeta(**data)


def snapshot_from_dict(data: dict) -> Snapshot:
    meta = _meta_from_dict(data["meta"])
    projects = {k: _project_from_dict(v) for k, v in data["projects"].items()}
    scans = {k: _scan_from_dict(v) for k, v in data["scans"].items()}
    findings = {k: _finding_from_dict(v) for k, v in data["findings"].items()}
    policies = [_policy_from_dict(p) for p in data["policies"]]
    return Snapshot(
        meta=meta,
        projects=projects,
        scans=scans,
        findings=findings,
        policies=policies,
    )


def _snapshot_body_dict(snapshot: Snapshot) -> dict:
    return {
        "projects": {k: asdict(v) for k, v in snapshot.projects.items()},
        "scans": {k: asdict(v) for k, v in snapshot.scans.items()},
        "findings": {k: asdict(v) for k, v in snapshot.findings.items()},
        "policies": [asdict(p) for p in snapshot.policies],
    }


def save_snapshot(snapshot: Snapshot, directory: Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    meta_path = directory / "meta.json"
    snapshot_path = directory / "snapshot.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(snapshot.meta), f, indent=2)
        f.write("\n")
    with snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(_snapshot_body_dict(snapshot), f, indent=2)
        f.write("\n")


def _load_from_directory(directory: Path) -> Snapshot:
    directory = Path(directory)
    meta_path = directory / "meta.json"
    snapshot_path = directory / "snapshot.json"
    if not meta_path.is_file() or not snapshot_path.is_file():
        raise SnapshotError(f"missing snapshot files in {directory}")
    with meta_path.open(encoding="utf-8") as f:
        meta = _meta_from_dict(json.load(f))
    with snapshot_path.open(encoding="utf-8") as f:
        body = json.load(f)
    return Snapshot(
        meta=meta,
        projects={k: _project_from_dict(v) for k, v in body["projects"].items()},
        scans={k: _scan_from_dict(v) for k, v in body["scans"].items()},
        findings={k: _finding_from_dict(v) for k, v in body["findings"].items()},
        policies=[_policy_from_dict(p) for p in body["policies"]],
    )


def load_snapshot(path: Path) -> Snapshot:
    path = Path(path)
    if path.is_dir():
        return _load_from_directory(path)
    if path.is_file():
        if path.name == "snapshot.json":
            return _load_from_directory(path.parent)
        raise SnapshotError(f"not a snapshot path: {path}")
    raise SnapshotError(f"not a snapshot path: {path}")


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def union_snapshots(snapshots: List[Snapshot]) -> Snapshot:
    if not snapshots:
        raise SnapshotError("no snapshots to union")

    namespace = snapshots[0].meta.namespace
    for snap in snapshots[1:]:
        if snap.meta.namespace != namespace:
            raise SnapshotError(
                f"mixed namespaces: {namespace!r} vs {snap.meta.namespace!r}"
            )

    projects: Dict[str, Project] = {}
    scans: Dict[str, Scan] = {}
    findings: Dict[str, Finding] = {}
    policies: List[Policy] = []
    policy_uuids = set()

    project_tags: List[str] = []
    mark_dates: Dict[str, str] = {}
    days = 0
    customer = ""
    decision_date: Optional[str] = None
    generated_at = ""
    ci_runs_dropped_no_pr = 0

    for snap in snapshots:
        for uuid, project in snap.projects.items():
            if uuid not in projects:
                projects[uuid] = project
        for uuid, scan in snap.scans.items():
            if uuid not in scans:
                scans[uuid] = scan
        for uuid, finding in snap.findings.items():
            if uuid not in findings:
                findings[uuid] = finding
        for policy in snap.policies:
            if policy.uuid not in policy_uuids:
                policy_uuids.add(policy.uuid)
                policies.append(policy)

        project_tags.extend(snap.meta.project_tags)
        for key, value in snap.meta.mark_dates.items():
            if key not in mark_dates:
                mark_dates[key] = value
        days = max(days, snap.meta.days)
        if not customer and snap.meta.customer:
            customer = snap.meta.customer
        if decision_date is None and snap.meta.decision_date is not None:
            decision_date = snap.meta.decision_date
        if snap.meta.generated_at > generated_at:
            generated_at = snap.meta.generated_at
        ci_runs_dropped_no_pr += snap.meta.ci_runs_dropped_no_pr

    meta = SnapshotMeta(
        namespace=namespace,
        project_tags=_unique_preserve_order(project_tags),
        days=days,
        mark_dates=mark_dates,
        customer=customer,
        decision_date=decision_date,
        generated_at=generated_at,
        ci_runs_dropped_no_pr=ci_runs_dropped_no_pr,
        project_count=len(projects),
    )
    return Snapshot(
        meta=meta,
        projects=projects,
        scans=scans,
        findings=findings,
        policies=policies,
    )


def load_snapshot_dir(directory: Path) -> Snapshot:
    directory = Path(directory)
    paths = sorted(directory.glob("*/snapshot.json"))
    snapshots: List[Snapshot] = []
    for snapshot_path in paths:
        if snapshot_path.parent.name.startswith("union-"):
            continue
        snapshots.append(_load_from_directory(snapshot_path.parent))
    if not snapshots:
        raise SnapshotError(f"no snapshots under {directory}")
    return union_snapshots(snapshots)
