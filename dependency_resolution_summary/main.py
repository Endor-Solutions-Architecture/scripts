"""Dependency Resolution & Reachability Summary report.

Member-facing port of the ewok report dependency_resolution_summary command.
Authenticates via `endorctl auth --print-access-token` and runs a single
graph query against POST /v1/namespaces/{ns}/queries.
"""

import argparse
import copy
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

try:
    from dependency_resolution_summary.pdf_generator import (
        generate_dependency_resolution_summary_pdf,
    )
except ImportError:
    # Fallback for when invoked as `python main.py` from inside the script directory
    from pdf_generator import generate_dependency_resolution_summary_pdf


def extract_first_sentence_smart(text: str) -> str:
    """Return the first sentence in ``text``.

    A sentence boundary is a period followed by a space and an uppercase
    letter. This avoids splitting on version numbers like "v4.5.2".
    """
    period_positions = [i for i, ch in enumerate(text) if ch == "."]
    for pos in period_positions:
        if pos + 2 < len(text):
            after = text[pos + 1 : pos + 3]
            if after[0] == " " and after[1].isupper():
                return text[: pos + 1]
        if pos == len(text) - 1:
            return text
    return text


def clean_description(description: str | None) -> str:
    """Collapse whitespace and keep the last 2 lines when ``description`` is multiline."""
    if not description:
        return ""
    lines = description.split("\n")
    cleaned = "\n".join(lines[-2:]) if len(lines) > 2 else description
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return " ".join(cleaned.split()).strip()


def get_error_message_from_analysis(error_analysis: dict) -> str:
    """Pick the best human-readable note from one ``error_analysis`` entry."""
    category = error_analysis.get("error_category", "")
    if category == "ERROR_CATEGORY_TOOLCHAIN":
        snippet = error_analysis.get("matching_snippet")
        if snippet:
            return extract_first_sentence_smart(snippet.strip())
        return ""
    notes = error_analysis.get("fixable_notes")
    return notes.strip() if notes else ""


_ERROR_BUCKETS = ("call_graph", "resolved", "unresolved")


def extract_error_message(resolution_errors: dict) -> str:
    """Walk call_graph -> resolved -> unresolved for the first non-empty message.

    For each bucket: try ``error_analysis[0]`` via ``get_error_message_from_analysis``;
    if that yields nothing, fall back to ``clean_description(description)`` for the
    same bucket; otherwise advance to the next bucket. Mirrors ewok's behaviour so
    the report stays a faithful port. Returns ``""`` if no bucket produces a message.
    """
    for bucket in _ERROR_BUCKETS:
        entry = resolution_errors.get(bucket)
        if not entry:
            continue
        analyses = entry.get("error_analysis") or []
        if analyses:
            msg = get_error_message_from_analysis(analyses[0])
            if msg:
                return msg
        description = entry.get("description")
        if description:
            return clean_description(description)
    return ""


_ENDOR_URL_TEMPLATE = (
    "https://app.endorlabs.com/t/{namespace}/projects/{uuid}"
    "/versions/default/inventory/packages"
)


def _count(refs: dict, key: str) -> int:
    return refs.get(key, {}).get("count_response", {}).get("count", 0) or 0


def _packages(refs: dict) -> list:
    return refs.get("PackageDetails", {}).get("list", {}).get("objects", []) or []


def _percentage(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0
    return round((numerator / denominator) * 100, 2)


def process_project(project: dict) -> dict:
    """Categorize a single project row from the graph query response."""
    uuid = project.get("uuid", "")
    tenant_meta = project.get("tenant_meta", {}) or {}
    meta = project.get("meta", {}) or {}
    refs = meta.get("references", {}) or {}
    namespace = tenant_meta.get("namespace", "")

    total = _count(refs, "TotalPackagesCount")
    dep_success = _count(refs, "DependencyResolutionSuccessCount")
    dep_failed = _count(refs, "DependencyResolutionFailedCount")
    reach_success = _count(refs, "ReachabilitySuccessCount")
    reach_failed = _count(refs, "ReachabilityFailedCount")

    if dep_failed > 0:
        category = "dependency_resolution_issues"
    elif reach_failed > 0:
        category = "reachability_issues_only"
    else:
        category = "full_success"

    packages = _packages(refs)
    reachability_strategy = ""
    if category in ("full_success", "reachability_issues_only"):
        has_precomputed = any(
            (pkg.get("spec", {}) or {}).get("precomputed_call_graph_state")
            == "PRECOMPUTED_STATE_SUCCESS"
            for pkg in packages
        )
        reachability_strategy = "PRE-COMPUTED" if has_precomputed else "FULL"

    error_notes = ""
    if category != "full_success":
        notes = set()
        for pkg in packages:
            errs = (pkg.get("spec", {}) or {}).get("resolution_errors") or {}
            if errs:
                msg = extract_error_message(errs)
                if msg:
                    notes.add(msg)
        if notes:
            error_notes = " | ".join(sorted(notes))

    return {
        "uuid": uuid,
        "namespace": namespace,
        "project_name": meta.get("name", ""),
        "project_url": _ENDOR_URL_TEMPLATE.format(namespace=namespace, uuid=uuid),
        "total_packages": total,
        "dependency_resolution_success": dep_success,
        "dependency_resolution_failed": dep_failed,
        "reachability_success": reach_success,
        "reachability_failed": reach_failed,
        "dependency_resolution_percentage": _percentage(dep_success, total),
        "reachability_percentage": _percentage(reach_success, total),
        "category": category,
        "reachability_strategy": reachability_strategy,
        "error_notes": error_notes,
        "tags": meta.get("tags", []) or [],
    }


CSV_HEADERS = [
    "Namespace",
    "Project UUID",
    "Project Name",
    "Project URL",
    "Total Packages",
    "Dependency Resolution Success",
    "Dependency Resolution Failed",
    "Reachability Success",
    "Reachability Failed",
    "Dependency Resolution %",
    "Reachability %",
    "Category",
    "Reachability Strategy",
    "Error Notes",
    "Tags",
]


def _row_to_csv(row: dict) -> list:
    return [
        row["namespace"],
        row["uuid"],
        row["project_name"],
        row["project_url"],
        row["total_packages"],
        row["dependency_resolution_success"],
        row["dependency_resolution_failed"],
        row["reachability_success"],
        row["reachability_failed"],
        row["dependency_resolution_percentage"],
        row["reachability_percentage"],
        row["category"],
        row["reachability_strategy"],
        row["error_notes"],
        # ewok writes the raw Python list repr (e.g. "[]" or "['prod', 'java']")
        repr(list(row.get("tags") or [])),
    ]


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        for r in rows:
            writer.writerow(_row_to_csv(r))


class AuthError(RuntimeError):
    """Raised when no token can be resolved."""


def resolve_token(explicit: str | None) -> str:
    """Return a JWT for REST calls. Order: --token, ENDOR_TOKEN, endorctl auth."""
    if explicit:
        return explicit
    env = os.environ.get("ENDOR_TOKEN")
    if env:
        return env
    try:
        result = subprocess.run(
            ["endorctl", "auth", "--print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AuthError(
            "endorctl is not installed. Install it or pass --token / set ENDOR_TOKEN."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AuthError(
            "endorctl auth failed — run `endorctl auth login` first, "
            "or set ENDOR_TOKEN. stderr:\n" + (exc.stderr or "")
        ) from exc
    return result.stdout.strip()


def fetch_all_projects(
    api_url: str,
    namespace: str,
    token: str,
    query: dict,
    page_size: int = 100,
) -> list[dict]:
    """POST the graph query and page through results, returning all project rows.

    The ``query`` argument is not mutated.
    """
    url = f"{api_url.rstrip('/')}/v1/namespaces/{namespace}/queries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    query = copy.deepcopy(query)
    list_params = query.setdefault("spec", {}).setdefault("query_spec", {}).setdefault(
        "list_parameters", {}
    )
    list_params["page_size"] = page_size
    list_params.pop("page_token", None)

    projects: list[dict] = []
    while True:
        resp = requests.post(url, json=query, headers=headers, timeout=300)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text}")
        body = resp.json()
        list_payload = (
            body.get("spec", {})
            .get("query_response", {})
            .get("list", {})
        )
        chunk = list_payload.get("objects", []) or []
        projects.extend(chunk)
        next_token = list_payload.get("response", {}).get("next_page_token")
        print(f"Fetched {len(projects)} projects so far...", file=sys.stderr)
        if not next_token:
            break
        list_params["page_token"] = next_token
    return projects


DEFAULT_API_URL = "https://api.endorlabs.com"


def _load_query() -> dict:
    here = Path(__file__).parent
    return json.loads((here / "query.dependency_resolution_summary.json").read_text())


def _output_paths(output_dir: Path, namespace: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"dependency_resolution_summary.{namespace}.{stamp}"
    return output_dir / f"{base}.csv", output_dir / f"{base}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Dependency Resolution & Reachability Summary report."
    )
    parser.add_argument("-n", "--namespace", required=True,
                        help="Tenant or sub-namespace; descendants are traversed.")
    parser.add_argument("--output-dir", default="generated_reports",
                        help="Where to write CSV/PDF (default: ./generated_reports)")
    parser.add_argument("--api-url",
                        default=os.environ.get("ENDOR_API_URL", DEFAULT_API_URL),
                        help="Endor API base URL (default: %(default)s)")
    parser.add_argument("--page-size", type=int, default=100,
                        help="Graph query page size (default: 100)")
    parser.add_argument("--token", default=None,
                        help="Override token; otherwise resolves from ENDOR_TOKEN "
                             "or `endorctl auth --print-access-token`.")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF rendering and only write the CSV.")
    args = parser.parse_args(argv)

    try:
        token = resolve_token(args.token)
    except AuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Fetching projects for namespace '{args.namespace}'...", file=sys.stderr)
    try:
        raw_projects = fetch_all_projects(
            api_url=args.api_url,
            namespace=args.namespace,
            token=token,
            query=_load_query(),
            page_size=args.page_size,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Got {len(raw_projects)} projects total. Processing...", file=sys.stderr)
    rows = [process_project(p) for p in raw_projects]

    csv_path, pdf_path = _output_paths(Path(args.output_dir), args.namespace)
    write_csv(rows, str(csv_path))
    print(f"Wrote CSV: {csv_path} ({len(rows)} rows)")

    if not args.no_pdf:
        generate_dependency_resolution_summary_pdf(str(pdf_path), args.namespace, rows)
        print(f"Wrote PDF: {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
