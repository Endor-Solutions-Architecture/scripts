#!/usr/bin/env python3
"""Bulk-assign (or clear) Project scan profiles from a CSV. Dry-run by default.

Requires the ``endorlabs`` Python SDK and credentials with list access to the
tenant. ``--apply`` additionally requires Project update permission on that
tenant (privileged-read / admin-read tokens are dry-run only).

See README.md in this directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from endorlabs import Client


def _dig(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        else:
            cur = getattr(cur, k, default)
    return cur


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump(mode="python", exclude_none=False)
    return {}


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _repo_slug_from_name(name: str | None) -> str | None:
    if not name:
        return None
    m = re.search(
        r"(?:github\.com[:/])(?P<owner>[^/]+)/(?P<repo>[^/\s.]+?)(?:\.git)?/?$",
        name.strip(),
        re.I,
    )
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    if "/" in name and not name.startswith("http"):
        return name.strip().removesuffix(".git")
    return None


@dataclass
class CsvRow:
    line_no: int
    raw: dict[str, str]
    repo: str = ""
    project_uuid: str = ""
    project_name: str = ""
    namespace_hint: str = ""
    current_profile_csv: str = ""


@dataclass
class ResolvedProject:
    row: CsvRow
    uuid: str = ""
    name: str = ""
    namespace: str = ""
    scan_profile_uuid: str = ""
    error: str = ""
    resource: Any = field(default=None, repr=False)


def _read_csv(path: Path) -> list[CsvRow]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"CSV has no header: {path}")
        field_map = {_norm_key(h): h for h in reader.fieldnames if h}

        def col(*aliases: str) -> str:
            for a in aliases:
                h = field_map.get(_norm_key(a))
                if h:
                    return h
            return ""

        c_repo = col("repo", "repository", "slug", "owner_repo")
        c_uuid = col("project_uuid", "uuid", "project_id")
        c_name = col("project_name", "meta_name", "name", "url")
        c_ns = col("namespace", "tenant_meta_namespace", "ns")
        c_sp = col("scan_profile_uuid", "current_scan_profile_uuid")

        rows: list[CsvRow] = []
        for i, raw in enumerate(reader, start=2):
            row = CsvRow(
                line_no=i,
                raw={k: (v or "").strip() for k, v in raw.items() if k},
                repo=(raw.get(c_repo) or "").strip() if c_repo else "",
                project_uuid=(raw.get(c_uuid) or "").strip() if c_uuid else "",
                project_name=(raw.get(c_name) or "").strip() if c_name else "",
                namespace_hint=(raw.get(c_ns) or "").strip() if c_ns else "",
                current_profile_csv=(raw.get(c_sp) or "").strip() if c_sp else "",
            )
            if not (row.project_uuid or row.repo or row.project_name):
                continue
            rows.append(row)
        return rows


def _dedupe_by_uuid(items: list[Any]) -> list[Any]:
    by_uuid: dict[str, Any] = {}
    for item in items:
        d = _as_dict(item)
        uid = str(d.get("uuid") or getattr(item, "uuid", "") or "")
        if uid and uid not in by_uuid:
            by_uuid[uid] = item
    return list(by_uuid.values())


def _resolve_scan_profile(client: Client, profile_ref: str) -> dict[str, Any]:
    ref = profile_ref.strip()
    if re.fullmatch(r"[0-9a-fA-F]{24}", ref) or re.fullmatch(
        r"[0-9a-fA-F-]{32,36}", ref
    ):
        candidates = client.ScanProfile.list(
            traverse=True, filter=f'uuid=="{ref}"', max_pages=1
        )
    else:
        candidates = client.ScanProfile.list(
            traverse=True, filter=f'meta.name=="{ref}"', max_pages=1
        )
        if not candidates:
            needle = ref.casefold()
            candidates = [
                p
                for p in client.ScanProfile.list(traverse=True)
                if str(_dig(_as_dict(p), "meta", "name") or "").casefold() == needle
            ]

    unique = _dedupe_by_uuid(list(candidates))
    if not unique:
        raise SystemExit(f"ScanProfile not found for ref={ref!r}")
    if len(unique) > 1:
        names = [
            f"{_dig(_as_dict(p), 'meta', 'name')}"
            f"@{_dig(_as_dict(p), 'tenant_meta', 'namespace')}"
            f"/{_as_dict(p).get('uuid')}"
            for p in unique
        ]
        raise SystemExit(f"Ambiguous ScanProfile ref={ref!r}: {names}")

    p = unique[0]
    d = _as_dict(p)
    return {
        "uuid": d.get("uuid") or getattr(p, "uuid", None),
        "name": _dig(d, "meta", "name"),
        "namespace": _dig(d, "tenant_meta", "namespace"),
        "resource": p,
    }


def _project_from_list_row(obj: Any, row: CsvRow) -> ResolvedProject:
    d = _as_dict(obj)
    return ResolvedProject(
        row=row,
        uuid=str(d.get("uuid") or getattr(obj, "uuid", "") or ""),
        name=str(_dig(d, "meta", "name") or ""),
        namespace=str(_dig(d, "tenant_meta", "namespace") or ""),
        scan_profile_uuid=str(_dig(d, "spec", "scan_profile_uuid") or ""),
        resource=obj,
    )


def _search_project(client: Client, query: str) -> list[Any]:
    q = query.strip()
    if not q:
        return []
    search = getattr(client.Project, "search_by_name", None)
    if callable(search):
        try:
            return list(search(q, traverse=True, max_pages=2))
        except TypeError:
            return list(search(q, traverse=True))
    return list(
        client.Project.list(
            traverse=True,
            filter=f'meta.name matches "{q}"',
            mask="uuid,meta.name,tenant_meta.namespace,spec.scan_profile_uuid",
            max_pages=2,
        )
    )


def _resolve_one_project(client: Client, row: CsvRow) -> ResolvedProject:
    out = ResolvedProject(row=row)
    try:
        if row.project_uuid:
            hits = client.Project.list(
                traverse=True,
                filter=f'uuid=="{row.project_uuid}"',
                mask="uuid,meta.name,tenant_meta.namespace,spec.scan_profile_uuid",
                max_pages=1,
            )
            if not hits and row.namespace_hint:
                hits = [
                    client.Project.get(row.project_uuid, namespace=row.namespace_hint)
                ]
            if not hits:
                out.error = "project_uuid_not_found"
                return out
            hits = _dedupe_by_uuid(list(hits))
            if len(hits) > 1:
                out.error = f"ambiguous_uuid_matches={len(hits)}"
                return out
            return _project_from_list_row(hits[0], row)

        slug = _repo_slug_from_name(row.repo) or _repo_slug_from_name(row.project_name)
        search_q = slug or row.project_name or row.repo
        hits = _search_project(client, search_q)
        if not hits and row.repo and row.repo != search_q:
            hits = _search_project(client, row.repo)
        if not hits:
            out.error = "project_not_found"
            return out

        chosen = None
        if slug:
            for h in hits:
                name = _dig(_as_dict(h), "meta", "name") or ""
                hit_slug = _repo_slug_from_name(str(name))
                if hit_slug and hit_slug.lower() == slug.lower():
                    chosen = h
                    break
        if chosen is None:
            hits = _dedupe_by_uuid(list(hits))
            if len(hits) > 1:
                out.error = f"ambiguous_name_matches={len(hits)}"
                return out
            chosen = hits[0]
        return _project_from_list_row(chosen, row)
    except Exception as exc:  # noqa: BLE001
        out.error = f"{type(exc).__name__}: {exc}"
        return out


def _resolve_projects_parallel(
    client: Client, rows: list[CsvRow], workers: int
) -> list[ResolvedProject]:
    results: list[ResolvedProject] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(_resolve_one_project, client, r) for r in rows]
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(key=lambda r: r.row.line_no)
    return results


def _write_result_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "repo",
        "project_uuid",
        "namespace",
        "project_name",
        "current_scan_profile_uuid",
        "target_scan_profile_uuid",
        "action",
        "status",
        "error",
        "mode",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Assign or clear Project scan profiles from a CSV. "
            "Dry-run by default; use --apply to write."
        )
    )
    p.add_argument(
        "csv",
        type=Path,
        help="CSV of projects (columns: repo and/or project_uuid and/or project_name)",
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "-sp",
        "--scan-profile",
        "--ScanProfile",
        dest="scan_profile",
        default=None,
        help="Target ScanProfile UUID or name (including a profile named Default)",
    )
    target.add_argument(
        "--clear",
        action="store_true",
        help=(
            "Clear scan_profile_uuid so the project inherits the tenant "
            "is_default profile (not the same as -sp Default)"
        ),
    )
    p.add_argument(
        "-b",
        "--batch",
        type=int,
        default=35,
        help="Max projects to change among rows not already on the target (default: 35)",
    )
    p.add_argument(
        "-n",
        "--tenant",
        "--namespace",
        dest="tenant",
        default=os.getenv("ENDOR_NAMESPACE") or "",
        help="Tenant root namespace (default: ENDOR_NAMESPACE)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (omit for dry-run). Requires Project update permission.",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Parallel workers for project resolve (default: 16)",
    )
    p.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Result CSV directory (default: <csv_dir>/bulk_set_results)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.csv.is_file():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 2
    if args.batch < 1:
        print("ERROR: --batch must be >= 1", file=sys.stderr)
        return 2
    tenant = (args.tenant or "").strip()
    if not tenant:
        print("ERROR: set -n/--tenant or ENDOR_NAMESPACE", file=sys.stderr)
        return 2

    client = Client(tenant=tenant)
    clear_to_default = bool(args.clear)
    if clear_to_default:
        target_uuid = ""
        profile_meta: dict[str, Any] = {
            "uuid": "",
            "name": "(inherit is_default)",
            "namespace": None,
        }
    else:
        profile_meta = _resolve_scan_profile(client, args.scan_profile)
        target_uuid = str(profile_meta["uuid"])

    print(
        json.dumps(
            {
                "tenant": tenant,
                "target_mode": "inherit_default" if clear_to_default else "set_profile",
                "scan_profile_uuid": target_uuid or None,
                "scan_profile_name": profile_meta.get("name"),
                "scan_profile_namespace": profile_meta.get("namespace"),
                "csv": str(args.csv),
                "batch": args.batch,
                "mode": "apply" if args.apply else "dry_run",
            },
            indent=2,
        )
    )

    rows = _read_csv(args.csv)
    resolved = _resolve_projects_parallel(client, rows, args.workers)

    result_rows: list[dict[str, Any]] = []
    to_change: list[ResolvedProject] = []

    for rp in resolved:
        repo = rp.row.repo or _repo_slug_from_name(rp.name) or ""
        current = rp.scan_profile_uuid or ""
        base = {
            "repo": repo,
            "project_uuid": rp.uuid,
            "namespace": rp.namespace,
            "project_name": rp.name,
            "current_scan_profile_uuid": current,
            "target_scan_profile_uuid": target_uuid,
            "mode": "apply" if args.apply else "dry_run",
            "action": "",
            "status": "",
            "error": rp.error,
        }
        if rp.error or not rp.uuid:
            base["action"] = "skip"
            base["status"] = "resolve_error"
            result_rows.append(base)
            continue
        already = (not current) if clear_to_default else (current == target_uuid)
        if already:
            base["action"] = "skip"
            base["status"] = "already_set"
            result_rows.append(base)
            continue
        to_change.append(rp)
        base["action"] = "pending_batch"
        base["status"] = "queued"
        result_rows.append(base)

    selected = to_change[: args.batch]
    selected_ids = {r.uuid for r in selected}
    deferred = to_change[args.batch :]

    for base in result_rows:
        if base["action"] != "pending_batch":
            continue
        if base["project_uuid"] in selected_ids:
            base["action"] = (
                "clear_scan_profile" if clear_to_default else "set_scan_profile"
            )
            base["status"] = "would_update" if not args.apply else "updating"
        else:
            base["action"] = "defer"
            base["status"] = "beyond_batch"

    for rp in selected:
        base = next(b for b in result_rows if b["project_uuid"] == rp.uuid)
        try:
            if not args.apply:
                base["status"] = "would_update"
            else:
                project = client.Project.get(rp.uuid, namespace=rp.namespace)
                project.spec.scan_profile_uuid = (
                    None if clear_to_default else target_uuid
                )
                client.Project.update(
                    project,
                    update_mask="spec.scan_profile_uuid",
                    namespace=rp.namespace,
                )
                base["status"] = "updated"
                base["current_scan_profile_uuid"] = target_uuid
        except Exception as exc:  # noqa: BLE001
            base["status"] = "error"
            base["error"] = f"{type(exc).__name__}: {exc}"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = args.results_dir or (args.csv.parent / "bulk_set_results")
    out_csv = results_dir / (
        f"bulk_set_{stamp}_{'apply' if args.apply else 'dryrun'}.csv"
    )
    _write_result_csv(out_csv, result_rows)

    summary = {
        "csv_rows": len(rows),
        "resolved_ok": sum(1 for r in resolved if r.uuid and not r.error),
        "resolve_errors": sum(1 for r in resolved if r.error or not r.uuid),
        "already_set": sum(1 for b in result_rows if b["status"] == "already_set"),
        "selected_this_batch": len(selected),
        "deferred_beyond_batch": len(deferred),
        "updated": sum(1 for b in result_rows if b["status"] == "updated"),
        "would_update": sum(1 for b in result_rows if b["status"] == "would_update"),
        "apply_errors": sum(1 for b in result_rows if b["status"] == "error"),
        "results_csv": str(out_csv),
    }
    print(json.dumps(summary, indent=2))
    return 1 if summary["apply_errors"] or summary["resolve_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
