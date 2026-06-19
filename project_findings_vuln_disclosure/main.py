"""Project Findings with Vulnerability Disclosure report.

Standalone port of ewok's `report project_findings_with_vulnerability_disclosure`.
Authenticates with an Endor Labs API key/secret pair (loaded from a `.env`
file or the process environment), runs a single graph query against
`POST /v1/namespaces/{ns}/queries`, pages through every project in the
namespace, and writes a CSV with the same columns produced by ewok.

Env vars (typically in `.env` next to this script):
  API_KEY            Endor Labs API key
  API_SECRET         Endor Labs API secret
  ENDOR_NAMESPACE    Tenant or sub-namespace to scan (descendants are traversed)
  ENDOR_API_URL      Optional; defaults to https://api.endorlabs.com
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import os
import sys
from datetime import date, datetime
from functools import reduce
from pathlib import Path
from typing import Any

import requests


DEFAULT_API_URL = "https://api.endorlabs.com"

CSV_HEADERS = [
    "Namespace",
    "Project UUID",
    "Project Name",
    "C",
    "H",
    "M",
    "L",
    "Last scan date",
    "Last month last scan date",
]

# Dot-paths into each (normalized) project record. Must stay aligned with
# CSV_HEADERS and with the ewok report definition.
FIELD_PATHS = [
    "tenant_meta.namespace",
    "uuid",
    "meta.name",
    "meta.references.CriticalFindingCount.count_response.count",
    "meta.references.HighFindingCount.count_response.count",
    "meta.references.MediumFindingCount.count_response.count",
    "meta.references.LowFindingCount.count_response.count",
    "meta.references.MostRecentScanResult.spec.start_time",
    "meta.references.LastPeriodScanResult.spec.start_time",
]


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_dotenv(path: Path) -> None:
    """Tiny `.env` loader. Sets variables in os.environ if not already set.

    Supports `KEY=VALUE` lines, `#` comments, blank lines, and optional
    single/double quotes around the value. Existing environment variables
    are NOT overridden — explicit shell env wins.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthError(RuntimeError):
    """Raised when API-key authentication fails."""


def authenticate(api_url: str, key: str, secret: str) -> str:
    """Exchange an API key/secret for a short-lived JWT bearer token."""
    url = f"{api_url.rstrip('/')}/v1/auth/api-key"
    try:
        resp = requests.post(
            url, json={"key": key, "secret": secret}, timeout=60
        )
    except requests.RequestException as exc:
        raise AuthError(f"Auth request to {url} failed: {exc}") from exc

    if resp.status_code != 200:
        raise AuthError(
            f"Auth failed ({resp.status_code}) at {url}: {resp.text}"
        )
    body = resp.json()
    token = body.get("token")
    if not token:
        raise AuthError(f"Auth response missing 'token': {body}")
    return token


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

# Hardcoded date windows that match the ewok query JSON byte-for-byte. The
# original ewok query has these baked in (no runtime date logic anywhere in
# ewok), so the no-flags behavior here is intentionally identical: same
# inputs in, same outputs out, for side-by-side comparison.
EWOK_FINDINGS_WINDOW = ("2025-12-01", "2025-12-31")
EWOK_LAST_PERIOD_WINDOW = ("2026-02-01", "2026-02-28")


def _month_range(value: str) -> tuple[str, str]:
    """Parse ``YYYY-MM`` into (first-of-month, last-of-month) ISO strings."""
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected YYYY-MM, got '{value}'"
        ) from exc
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    start = date(parsed.year, parsed.month, 1).isoformat()
    end = date(parsed.year, parsed.month, last_day).isoformat()
    return start, end


def _load_query_template() -> str:
    here = Path(__file__).parent
    return (
        here / "query.project_findings_with_vulnerability_disclosure.json"
    ).read_text()


def build_query(
    findings_range: tuple[str, str],
    last_period_range: tuple[str, str],
) -> dict:
    """Render the query template by substituting the date placeholders."""
    template = _load_query_template()
    rendered = (
        template
        .replace("__FINDINGS_START__", findings_range[0])
        .replace("__FINDINGS_END__", findings_range[1])
        .replace("__LAST_PERIOD_START__", last_period_range[0])
        .replace("__LAST_PERIOD_END__", last_period_range[1])
    )
    return json.loads(rendered)


# ---------------------------------------------------------------------------
# Result normalization & extraction (mirrors ewok behavior)
# ---------------------------------------------------------------------------

def normalize_record(record: dict) -> dict:
    """Flatten `meta.references[X].list.objects[0]` up into `meta.references[X]`.

    This matches `EwokReport.normalize_query_results` so the same dot-paths
    used by the ewok report definition continue to work.
    """
    references = (record.get("meta") or {}).get("references") or {}
    for props in references.values():
        objects = (props.get("list") or {}).get("objects") or []
        if objects:
            props.update(objects[0])
    return record


def get_report_value(d: dict, key: str, default: Any = None) -> Any:
    """Dot-path lookup; returns ``default`` (None) if any segment is missing."""
    return reduce(
        lambda acc, segment: acc[segment] if acc and segment in acc else None,
        key.split("."),
        d,
    ) if d is not None else default


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def fetch_all_projects(
    api_url: str,
    namespace: str,
    token: str,
    query: dict,
    page_size: int,
    request_timeout: int = 300,
) -> list[dict]:
    """POST the graph query and page through every project row."""
    url = f"{api_url.rstrip('/')}/v1/namespaces/{namespace}/queries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "12000",
    }

    list_params = (
        query.setdefault("spec", {})
        .setdefault("query_spec", {})
        .setdefault("list_parameters", {})
    )
    list_params["page_size"] = page_size
    list_params.pop("page_token", None)

    projects: list[dict] = []
    while True:
        resp = requests.post(
            url, json=query, headers=headers, timeout=request_timeout
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"HTTP {resp.status_code} from {url}: {resp.text}"
            )
        body = resp.json()
        list_payload = (
            body.get("spec", {}).get("query_response", {}).get("list", {})
        )
        chunk = list_payload.get("objects", []) or []
        for raw in chunk:
            projects.append(normalize_record(raw))
        print(
            f"Fetched {len(projects)} projects so far...", file=sys.stderr
        )
        next_token = (list_payload.get("response") or {}).get("next_page_token")
        if not next_token:
            break
        list_params["page_token"] = next_token
    return projects


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def project_to_row(project: dict) -> list[Any]:
    row: list[Any] = []
    for path in FIELD_PATHS:
        value = get_report_value(project, path)
        row.append("" if value is None else value)
    return row


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, dialect="excel")
        writer.writerow(CSV_HEADERS)
        for project in rows:
            writer.writerow(project_to_row(project))


def _output_path(output_dir: Path, namespace: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / (
        f"project_findings_with_vulnerability_disclosure.{namespace}.{stamp}.csv"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recreate the 'Project Findings with Vulnerability Disclosure' "
            "report as a standalone Python script."
        )
    )
    parser.add_argument(
        "--env-file",
        default=str(Path(__file__).parent / ".env"),
        help="Path to .env file (default: ./.env next to this script).",
    )
    parser.add_argument(
        "-n",
        "--namespace",
        default=None,
        help="Override ENDOR_NAMESPACE from the .env file.",
    )
    parser.add_argument(
        "--findings-month",
        type=_month_range,
        default=None,
        metavar="YYYY-MM",
        help=(
            "Calendar month used for FINDING_LEVEL_* date filters "
            "(default: %s..%s, mirroring the ewok JSON)."
            % EWOK_FINDINGS_WINDOW
        ),
    )
    parser.add_argument(
        "--last-period-month",
        type=_month_range,
        default=None,
        metavar="YYYY-MM",
        help=(
            "Calendar month used for the LastPeriodScanResult window "
            "(default: %s..%s, mirroring the ewok JSON)."
            % EWOK_LAST_PERIOD_WINDOW
        ),
    )
    parser.add_argument(
        "--month",
        type=_month_range,
        default=None,
        metavar="YYYY-MM",
        help=(
            "Shortcut: set both --findings-month and --last-period-month "
            "to the same calendar month."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="generated_reports",
        help="Where to write the CSV (default: ./generated_reports).",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Endor API base URL (default: ENDOR_API_URL or %s)."
        % DEFAULT_API_URL,
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=25,
        help=(
            "Graph query page size (default: 25). Lower this if you hit "
            "504 timeouts on large namespaces."
        ),
    )
    parser.add_argument(
        "--dump-query",
        action="store_true",
        help=(
            "Print the rendered query JSON to stdout and exit without "
            "calling the API."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    load_dotenv(Path(args.env_file))

    namespace = args.namespace or os.environ.get("ENDOR_NAMESPACE")
    if not namespace:
        print(
            "ERROR: namespace is required. Set ENDOR_NAMESPACE in .env or "
            "pass --namespace.",
            file=sys.stderr,
        )
        return 1

    findings_range = (
        args.findings_month or args.month or EWOK_FINDINGS_WINDOW
    )
    last_period_range = (
        args.last_period_month or args.month or EWOK_LAST_PERIOD_WINDOW
    )

    query = build_query(findings_range, last_period_range)
    query.setdefault("tenant_meta", {})["namespace"] = namespace

    if args.dump_query:
        print(json.dumps(query, indent=2))
        return 0

    api_key = os.environ.get("API_KEY")
    api_secret = os.environ.get("API_SECRET")
    if not api_key or not api_secret:
        print(
            "ERROR: API_KEY and API_SECRET must be set (via .env or env vars).",
            file=sys.stderr,
        )
        return 1

    api_url = (
        args.api_url
        or os.environ.get("ENDOR_API_URL")
        or DEFAULT_API_URL
    )

    print(
        f"Authenticating against {api_url} as namespace '{namespace}'...",
        file=sys.stderr,
    )
    try:
        token = authenticate(api_url, api_key, api_secret)
    except AuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Findings window:     {findings_range[0]} .. {findings_range[1]}",
        file=sys.stderr,
    )
    print(
        f"Last-period window:  {last_period_range[0]} .. {last_period_range[1]}",
        file=sys.stderr,
    )
    print(
        f"Fetching projects for namespace '{namespace}' (page size {args.page_size})...",
        file=sys.stderr,
    )
    try:
        projects = fetch_all_projects(
            api_url=api_url,
            namespace=namespace,
            token=token,
            query=query,
            page_size=args.page_size,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    csv_path = _output_path(Path(args.output_dir), namespace)
    write_csv(projects, csv_path)
    print(f"Wrote CSV: {csv_path} ({len(projects)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
