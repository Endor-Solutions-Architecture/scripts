from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from analyze import analyze
from collect import CollectError, collect
from render_csv import LabelError, read_labels_csv, write_csvs, write_summary
from render_pdf import write_pdf
from snapshot import Snapshot, SnapshotError, load_snapshot, load_snapshot_dir, save_snapshot


def parse_mark_dates(values: List[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(1)
        key, date = raw.split("=", 1)
        key = key.strip()
        date = date.strip()
        if not key:
            raise SystemExit(1)
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(1)
        parsed[key] = date
    return parsed


def parse_project_tags(raw: str) -> List[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def output_root(namespace: str) -> Path:
    return Path("generated_reports") / "block_mode_readiness" / namespace


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _reserve_output_dir(parent: Path, name: str) -> Path:
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    suffix = 0
    while True:
        candidate_name = name if suffix == 0 else f"{name}-{suffix}"
        candidate = parent / candidate_name
        try:
            candidate.mkdir(exist_ok=False)
        except FileExistsError:
            suffix += 1
            continue
        return candidate


def _warn_if_days_exceed_retention(days: int) -> None:
    if days > 21:
        print(
            "warning: --days exceeds 21-day API retention; older scans will not be returned",
            file=sys.stderr,
        )


def _snapshot_dir_count(directory: Path) -> int:
    return sum(
        1
        for path in Path(directory).glob("*/snapshot.json")
        if not path.parent.name.startswith("union-")
    )


def _write_report_files(
    snapshot: Snapshot,
    directory: Path,
    labels: Optional[List[Dict[str, str]]] = None,
    snapshot_count: int = 1,
) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    analysis = analyze(snapshot, labels=labels, snapshot_count=snapshot_count)
    write_csvs(analysis, directory)
    write_summary(analysis, snapshot, directory)
    write_pdf(analysis, snapshot, directory / "readiness_report.pdf")
    return directory


def cmd_collect(args: Any) -> Path:
    _warn_if_days_exceed_retention(args.days)
    tags = parse_project_tags(args.project_tags)
    mark_dates = parse_mark_dates(args.mark_date or [])
    snapshot = collect(
        args.namespace,
        tags,
        args.days,
        mark_dates=mark_dates,
        customer=args.customer,
        decision_date=args.decision_date,
    )
    out = _reserve_output_dir(output_root(args.namespace), _timestamp())
    save_snapshot(snapshot, out)
    return out


def cmd_report(args: Any) -> Path:
    labels = None
    if args.labels:
        labels = read_labels_csv(Path(args.labels))
    if args.snapshot:
        path = Path(args.snapshot)
        snapshot = load_snapshot(path)
        out = path if path.is_dir() else path.parent
        return _write_report_files(snapshot, out, labels=labels, snapshot_count=1)
    directory = Path(args.snapshot_dir)
    snapshot = load_snapshot_dir(directory)
    out = _reserve_output_dir(directory, "union-" + _timestamp())
    return _write_report_files(
        snapshot,
        out,
        labels=labels,
        snapshot_count=_snapshot_dir_count(directory),
    )


def cmd_run(args: Any) -> Path:
    out = cmd_collect(args)
    snapshot = load_snapshot(out)
    return _write_report_files(snapshot, out, snapshot_count=1)


def _add_collect_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-n", "--namespace", required=True)
    parser.add_argument("--project-tags", required=True)
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--mark-date", action="append")
    parser.add_argument("--customer")
    parser.add_argument("--decision-date")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    collect_parser = subparsers.add_parser("collect")
    _add_collect_flags(collect_parser)

    report_parser = subparsers.add_parser("report")
    source = report_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot")
    source.add_argument("--snapshot-dir")
    report_parser.add_argument("--labels")

    run_parser = subparsers.add_parser("run")
    _add_collect_flags(run_parser)
    return parser


def _exit_code(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return _exit_code(exc)

    handlers = {
        "collect": cmd_collect,
        "report": cmd_report,
        "run": cmd_run,
    }
    try:
        handlers[args.command](args)
    except CollectError as exc:
        if exc.command:
            print(" ".join(str(part) for part in exc.command), file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    except (SnapshotError, LabelError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SystemExit as exc:
        return _exit_code(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
