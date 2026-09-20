from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from classify import (
    classify_finding,
    classify_outcome,
    derive_fixable,
    derive_reachability,
    extract_policy_name,
    extract_pr_number,
)
from snapshot import Finding, Policy, Project, Scan, Snapshot, SnapshotMeta

CHUNK = 80

PROJECT_FIELD_MASK = (
    "uuid,meta.tags,tenant_meta.namespace,spec.git.full_name,spec.git.http_clone_url"
)
POLICY_FIELD_MASK = (
    "uuid,meta.name,spec.project_selector,spec.project_exceptions,"
    "spec.disable,spec.policy_type"
)
SCAN_FIELD_MASK = (
    "uuid,meta.create_time,meta.parent_uuid,meta.tags,tenant_meta.namespace,"
    "context.tags,spec.status,spec.blocking_findings,spec.warning_findings,"
    "spec.policies_triggered"
)
FINDING_FIELD_MASK = (
    "uuid,meta.name,meta.description,spec.level,spec.finding_categories,"
    "spec.finding_tags,spec.finding_metadata.vulnerability.meta.name,"
    "spec.project_uuid,tenant_meta.namespace,"
    "spec.finding_metadata.vulnerability.spec.affected,"
    "spec.target_dependency_package_name"
)


class CollectError(Exception):
    def __init__(self, message: str, command: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.command = command


def _full_command(args: List[str], namespace: str) -> List[str]:
    return ["endorctl", "-n", namespace] + list(args)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cutoff_iso(days: int) -> str:
    when = datetime.now(timezone.utc) - timedelta(days=days)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _objects(response: Any, command: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(response, dict):
        raise CollectError(
            "malformed list.objects response: top-level value is not an object",
            command=command,
        )
    list_value = response.get("list")
    if not isinstance(list_value, dict):
        raise CollectError(
            "malformed list.objects response: list is missing or not an object",
            command=command,
        )
    if "objects" not in list_value:
        raise CollectError(
            "malformed list.objects response: objects is missing",
            command=command,
        )
    objects = list_value["objects"]
    if not isinstance(objects, list):
        raise CollectError(
            "malformed list.objects response: objects is not a list",
            command=command,
        )
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise CollectError(
                f"malformed list.objects response: item {index} is not an object",
                command=command,
            )
    return objects


def _in_clause(field: str, uuids: Iterable[str]) -> str:
    quoted = "', '".join(uuids)
    return f"{field} in ['{quoted}']"


def _chunks(items: List[str], size: int) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _base_url(clone_url: str) -> str:
    if not clone_url:
        return ""
    url = clone_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def _severity(level: str) -> str:
    prefix = "FINDING_LEVEL_"
    if level.startswith(prefix):
        return level[len(prefix) :]
    return level


def _package_from_affected(affected: Any) -> str:
    if not affected:
        return ""
    if isinstance(affected, str):
        return affected
    if isinstance(affected, dict):
        package = affected.get("package")
        if isinstance(package, dict):
            return package.get("name") or ""
        if isinstance(package, str) and package:
            return package
        name = affected.get("name")
        if isinstance(name, str) and name:
            return name
        return ""
    if isinstance(affected, list):
        for item in affected:
            name = _package_from_affected(item)
            if name:
                return name
    return ""


def _policy_applies(obj: Dict[str, Any], projects: Iterable[Project]) -> bool:
    spec = obj.get("spec") or {}
    if spec.get("disable"):
        return False
    selector = set(spec.get("project_selector") or [])
    exceptions = set(spec.get("project_exceptions") or [])
    for project in projects:
        if project.uuid in exceptions:
            continue
        if not selector or selector.intersection(project.tags):
            return True
    return False


def _project_from_obj(obj: Dict[str, Any]) -> Project:
    git = (obj.get("spec") or {}).get("git") or {}
    return Project(
        uuid=obj.get("uuid") or "",
        full_name=git.get("full_name") or "",
        base_url=_base_url(git.get("http_clone_url") or ""),
        namespace=(obj.get("tenant_meta") or {}).get("namespace") or "",
        tags=list((obj.get("meta") or {}).get("tags") or []),
    )


def _policy_from_obj(obj: Dict[str, Any]) -> Policy:
    spec = obj.get("spec") or {}
    return Policy(
        uuid=obj.get("uuid") or "",
        name=(obj.get("meta") or {}).get("name") or "",
        selector_tags=list(spec.get("project_selector") or []),
        disabled=bool(spec.get("disable")),
    )


def _scan_from_obj(
    obj: Dict[str, Any],
    policy_names: Optional[Dict[str, str]] = None,
) -> Scan:
    spec = obj.get("spec") or {}
    meta = obj.get("meta") or {}
    return Scan(
        uuid=obj.get("uuid") or "",
        create_time=meta.get("create_time") or "",
        project_uuid=meta.get("parent_uuid") or "",
        pr_number=extract_pr_number(obj),
        outcome=classify_outcome(obj),
        warning_finding_ids=list(spec.get("warning_findings") or []),
        blocking_finding_ids=list(spec.get("blocking_findings") or []),
        status=spec.get("status") or "",
        namespace=(obj.get("tenant_meta") or {}).get("namespace") or "",
        policy_name=extract_policy_name(obj, policy_names),
    )


def _finding_from_obj(obj: Dict[str, Any]) -> Finding:
    spec = obj.get("spec") or {}
    meta = obj.get("meta") or {}
    tags = spec.get("finding_tags") or []
    vuln = ((spec.get("finding_metadata") or {}).get("vulnerability") or {})
    vuln_meta = vuln.get("meta") or {}
    vuln_spec = vuln.get("spec") or {}
    package = spec.get("target_dependency_package_name") or ""
    if not package:
        package = _package_from_affected(vuln_spec.get("affected"))
    vuln_id = vuln_meta.get("name") or ""
    return Finding(
        uuid=obj.get("uuid") or "",
        violation_type=classify_finding(obj),
        severity=_severity(spec.get("level") or ""),
        description=meta.get("description") or "",
        vuln_id=vuln_id,
        rule_id="" if vuln_id else (meta.get("name") or ""),
        package=package or "",
        reachable=derive_reachability(tags),
        fix_available=derive_fixable(tags),
        namespace=(obj.get("tenant_meta") or {}).get("namespace") or "",
    )


def run_endorctl(args: List[str], namespace: str, timeout: int = 120) -> Dict[str, Any]:
    cmd = _full_command(args, namespace)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CollectError(f"endorctl not found: {exc}", command=cmd) from exc
    except subprocess.CalledProcessError as exc:
        raise CollectError(f"endorctl failed: {exc.stderr}", command=cmd) from exc
    except subprocess.TimeoutExpired as exc:
        raise CollectError("endorctl timed out", command=cmd) from exc
    try:
        if not result.stdout or not result.stdout.strip():
            raise CollectError("empty endorctl output", command=cmd)
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CollectError(f"invalid JSON from endorctl: {exc}", command=cmd) from exc
    if not isinstance(parsed, dict):
        raise CollectError("endorctl JSON was not an object", command=cmd)
    return parsed


def _call_runner(
    runner: Callable[..., Dict[str, Any]],
    args: List[str],
    namespace: str,
    timeout: int = 120,
    validator: Optional[Callable[[Any, List[str]], Any]] = None,
) -> Any:
    last: Optional[BaseException] = None
    command = _full_command(args, namespace)
    for attempt in range(2):
        try:
            result = runner(args, namespace, timeout)
            if result is None:
                raise CollectError(
                    "endorctl returned no data",
                    command=command,
                )
            if validator is not None:
                return validator(result, command)
            return result
        except CollectError as exc:
            last = exc
            if attempt == 1:
                raise
        except Exception as exc:
            last = CollectError(str(exc), command=command)
            if attempt == 1:
                raise last from exc
    if last is None:
        raise CollectError("endorctl query failed", command=command)
    if isinstance(last, CollectError):
        raise last
    raise CollectError(str(last), command=_full_command(args, namespace)) from last


def _list_kind(
    runner: Callable[..., Dict[str, Any]],
    kind: str,
    filter_expr: str,
    field_mask: str,
    namespace: str,
    timeout: int = 120,
    required_uuids: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    args = [
        "api",
        "list",
        "-r",
        kind,
        "--filter",
        filter_expr,
        "--field-mask",
        field_mask,
        "--list-all",
        "--traverse",
    ]
    required = set(required_uuids or [])

    def validate(response: Any, command: List[str]) -> List[Dict[str, Any]]:
        objects = _objects(response, command)
        if required:
            returned = {
                obj.get("uuid")
                for obj in objects
                if isinstance(obj.get("uuid"), str) and obj.get("uuid")
            }
            missing = sorted(required - returned)
            if missing:
                raise CollectError(
                    "Finding response missing requested UUIDs: " + ", ".join(missing),
                    command=command,
                )
        return objects

    return _call_runner(
        runner,
        args,
        namespace,
        timeout,
        validator=validate,
    )


def collect(
    namespace: str,
    project_tags: List[str],
    days: int,
    *,
    mark_dates: Optional[Dict[str, str]] = None,
    customer: Optional[str] = None,
    decision_date: Optional[str] = None,
    generated_at: Optional[str] = None,
    runner: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Snapshot:
    query = runner or run_endorctl
    projects: Dict[str, Project] = {}
    for tag in project_tags:
        for obj in _list_kind(
            query,
            "Project",
            f"meta.tags matches '{tag}'",
            PROJECT_FIELD_MASK,
            namespace,
        ):
            uuid = obj.get("uuid") or ""
            if uuid and uuid not in projects:
                projects[uuid] = _project_from_obj(obj)

    if not projects:
        raise CollectError(f"no projects matched project tags: {', '.join(project_tags)}")

    policies: List[Policy] = []
    policy_names: Dict[str, str] = {}
    for obj in _list_kind(
        query,
        "Policy",
        "spec.policy_type == POLICY_TYPE_ADMISSION",
        POLICY_FIELD_MASK,
        namespace,
    ):
        uuid = obj.get("uuid") or ""
        name = (obj.get("meta") or {}).get("name") or ""
        if uuid and name:
            policy_names[uuid] = name
        if _policy_applies(obj, projects.values()):
            policies.append(_policy_from_obj(obj))

    cutoff = _cutoff_iso(days)
    scan_objs: List[Dict[str, Any]] = []
    parent_uuids = list(projects.keys())
    for chunk in _chunks(parent_uuids, CHUNK):
        filter_expr = (
            f'(context.type == "CONTEXT_TYPE_CI_RUN" and '
            f"{_in_clause('meta.parent_uuid', chunk)} and "
            f'meta.create_time > date("{cutoff}"))'
        )
        args = [
            "api",
            "list",
            "-r",
            "ScanResult",
            "--filter",
            filter_expr,
            "--field-mask",
            SCAN_FIELD_MASK,
            "--sort-path",
            "meta.create_time",
            "--sort-order",
            "descending",
            "--list-all",
            "--traverse",
            "-t",
            "300s",
        ]
        scan_objs.extend(
            _call_runner(
                query,
                args,
                namespace,
                360,
                validator=_objects,
            )
        )

    scans: Dict[str, Scan] = {}
    ci_runs_dropped_no_pr = 0
    for obj in scan_objs:
        scan = _scan_from_obj(obj, policy_names)
        if not scan.pr_number:
            ci_runs_dropped_no_pr += 1
            continue
        if scan.uuid and scan.uuid not in scans:
            scans[scan.uuid] = scan

    finding_ids: List[str] = []
    seen_findings = set()
    for scan in scans.values():
        for finding_id in scan.warning_finding_ids + scan.blocking_finding_ids:
            if finding_id and finding_id not in seen_findings:
                seen_findings.add(finding_id)
                finding_ids.append(finding_id)

    findings: Dict[str, Finding] = {}
    for chunk in _chunks(finding_ids, CHUNK):
        for obj in _list_kind(
            query,
            "Finding",
            _in_clause("uuid", chunk),
            FINDING_FIELD_MASK,
            namespace,
            required_uuids=chunk,
        ):
            uuid = obj.get("uuid") or ""
            if uuid and uuid not in findings:
                findings[uuid] = _finding_from_obj(obj)

    meta = SnapshotMeta(
        namespace=namespace,
        project_tags=list(project_tags),
        days=days,
        mark_dates=dict(mark_dates or {}),
        customer=namespace if customer is None else customer,
        decision_date=decision_date,
        generated_at=generated_at or _now_iso(),
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
