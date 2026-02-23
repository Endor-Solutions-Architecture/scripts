#!/usr/bin/env python3
"""
Generate a remediated findings report from the FindingLog API.

Fetches remediated finding logs (OPERATION_DELETE) within a date range via the
finding-logs list API, enriches with PackageVersion (relative_path, code_owners)
and Vulnerabilities (CVE from GHSA in description), and writes a CSV report.
No CSV input required—all data comes from FindingLog, PackageVersion, and
Vulnerabilities APIs.

Usage:
    python generate_remediation_report.py --start-date 2026-01-01 --end-date 2026-01-31 --output report.csv
    python generate_remediation_report.py --start-date 2026-01-01 --end-date 2026-01-31 --output report.csv --project-uuid xxxxxxxxxxxxxxxx
"""

import csv
import os
import re
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.endorlabs.com/v1"
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")

# GHSA ID pattern (e.g. GHSA-9965-vmph-33xx)
GHSA_PATTERN = re.compile(r"GHSA-[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+")
# CVE ID pattern (e.g. CVE-2025-56200)
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+")

# Field masks: fetch only required fields from each API
FINDING_LOGS_MASK = (
    "uuid,meta.description,meta.parent_uuid,spec.finding_uuid,spec.level,"
    "spec.finding_parent_name,spec.finding_parent_uuid,spec.introduced_at,"
    "spec.resolved_at,spec.days_unresolved,spec.finding_tags,spec.finding_categories,"
    "spec.ecosystem,tenant_meta.namespace"
)
VULNERABILITIES_MASK = "meta.name"
PACKAGE_VERSIONS_MASK = "uuid,spec.relative_path,spec.code_owners.owners"

# CSV output headers (display titles)
OUTPUT_COLUMNS = [
    "Finding Log UUID",
    "Finding UUID",
    "CVE ID",
    "Description",
    "Criticality",
    "Package/Application",
    "Package Location",
    "Code Owners",
    "Introduced At",
    "Resolved At",
    "Days Unresolved",
    "Tags",
    "Category",
    "Ecosystem",
    "Project UUID",
    "Namespace",
]


def get_token() -> str:
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        raise ValueError("API_KEY and API_SECRET must be set in environment")
    url = f"{API_URL}/auth/api-key"
    payload = {"key": api_key, "secret": api_secret}
    headers = {"Content-Type": "application/json", "Request-Timeout": "60"}
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")
    token = response.json().get("token")
    if not token:
        raise Exception("No token in API response")
    return token


def parse_date_to_iso(date_str: str, end_of_day: bool = False) -> str:
    """Parse YYYY-MM-DD to ISO 8601 string for API filter."""
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_finding_logs_filter(
    start_date: str,
    end_date: str,
    project_uuid: Optional[str] = None,
) -> str:
    """Build filter for remediated finding logs within date range."""
    start_iso = parse_date_to_iso(start_date, end_of_day=False)
    end_iso = parse_date_to_iso(end_date, end_of_day=True)
    filters = [
        "context.type==CONTEXT_TYPE_MAIN",
        "spec.operation==OPERATION_DELETE",
        "spec.finding_categories contains FINDING_CATEGORY_VULNERABILITY",
        "spec.finding_tags contains FINDING_TAGS_NORMAL",
        f"meta.create_time >= date({start_iso})",
        f"meta.create_time <= date({end_iso})",
    ]
    if project_uuid:
        filters.append(f'meta.parent_uuid=="{project_uuid}"')
    return " and ".join(filters)


def fetch_finding_logs(
    namespace: str,
    filter_str: str,
    headers: Dict[str, str],
    page_size: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch all finding logs matching the filter; paginate through results.
    Returns list of finding log objects.
    """
    url = f"{API_URL}/namespaces/{namespace}/finding-logs"
    objects: List[Dict[str, Any]] = []
    next_page_id = None
    while True:
        params = {
            "list_parameters.filter": filter_str,
            "list_parameters.mask": FINDING_LOGS_MASK,
            "list_parameters.page_size": str(page_size),
        }
        if next_page_id is not None:
            params["list_parameters.page_id"] = next_page_id
        response = requests.get(url, headers=headers, params=params, timeout=600)
        if response.status_code != 200:
            print(
                f"Finding-logs API error: {response.status_code} - {response.text}",
                file=sys.stderr,
            )
            raise RuntimeError(f"Finding-logs API failed: {response.status_code}")
        data = response.json()
        batch = data.get("list", {}).get("objects", [])
        objects.extend(batch)
        next_page_id = data.get("list", {}).get("response", {}).get("next_page_id")
        if not next_page_id:
            break
    return objects


def get_package_version_relative_paths_and_code_owners(
    namespace: str,
    package_version_uuids: List[str],
    headers: Dict[str, str],
    batch_size: int = 100,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Fetch package-versions by uuid; return (package_version_uuid -> spec.relative_path,
    package_version_uuid -> spec.code_owners).
    """
    relative_paths: Dict[str, str] = {}
    code_owners_map: Dict[str, str] = {}
    if not package_version_uuids:
        return relative_paths, code_owners_map
    url = f"{API_URL}/namespaces/{namespace}/package-versions"
    for i in range(0, len(package_version_uuids), batch_size):
        batch = package_version_uuids[i : i + batch_size]
        uuid_list = "', '".join(batch)
        filter_str = f"uuid in ['{uuid_list}']"
        next_page_id = None
        while True:
            params = {
                "list_parameters.filter": filter_str,
                "list_parameters.mask": PACKAGE_VERSIONS_MASK,
                "list_parameters.page_size": "500",
            }
            if next_page_id is not None:
                params["list_parameters.page_id"] = next_page_id
            response = requests.get(url, headers=headers, params=params, timeout=600)
            if response.status_code != 200:
                print(
                    f"Package-versions API error: {response.status_code} - {response.text}",
                    file=sys.stderr,
                )
                raise RuntimeError(
                    f"Package-versions API failed: {response.status_code}"
                )
            data = response.json()
            objs = data.get("list", {}).get("objects", [])
            for obj in objs:
                uid = obj.get("uuid")
                if not uid:
                    continue
                spec = obj.get("spec") or {}
                rel_path = spec.get("relative_path") or ""
                relative_paths[uid] = (
                    rel_path.strip() if isinstance(rel_path, str) else str(rel_path)
                )
                code_owners_obj = spec.get("code_owners") or {}
                code_owners = code_owners_obj.get("owners")
                if code_owners is None:
                    code_owners_map[uid] = ""
                elif isinstance(code_owners, list):
                    code_owners_map[uid] = ", ".join(str(x) for x in code_owners)
                else:
                    code_owners_map[uid] = str(code_owners)
            next_page_id = data.get("list", {}).get("response", {}).get("next_page_id")
            if not next_page_id:
                break
    return relative_paths, code_owners_map


def format_list_field(val: Any) -> str:
    """Format list/array field for CSV output."""
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


def extract_ghsa_id(description: str) -> Optional[str]:
    """Extract the first GHSA ID from a string, or None if not found."""
    if not description or description == "missing":
        return None
    match = GHSA_PATTERN.search(description)
    return match.group(0) if match else None


def extract_cve_id(description: str) -> Optional[str]:
    """Extract the first CVE ID from a string, or None if not found."""
    if not description or description == "missing":
        return None
    match = CVE_PATTERN.search(description)
    return match.group(0) if match else None


def fetch_cve(
    ghsa_id: str,
    headers: Dict[str, str],
    namespace: str = "oss",
) -> Optional[str]:
    """
    Query the vulnerabilities API by GHSA ID and return the CVE ID (meta.name of first object).
    """
    url = f"{API_URL}/namespaces/{namespace}/queries/vulnerabilities"
    payload = {
        "meta": {"name": f"ListVulnerabilitiesQuery(namespace:{namespace})"},
        "spec": {
            "vulnerability_name_query": {"name": ghsa_id},
            "mask": VULNERABILITIES_MASK,
        },
    }
    response = requests.post(
        url,
        headers={
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if response.status_code != 200:
        return None
    data = response.json()
    objects = (data.get("response") or {}).get("list", {}).get("objects", [])
    if not objects:
        return None
    return (objects[0].get("meta") or {}).get("name")


def write_csv_rows(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate remediated findings report from FindingLog API."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Report start date (YYYY-MM-DD). Finding logs with meta.create_time >= this date.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="Report end date (YYYY-MM-DD). Finding logs with meta.create_time <= end of this date.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV report path.",
    )
    parser.add_argument(
        "--project-uuid",
        default=None,
        help="Optional project UUID to filter findings to a single project.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of package_version UUIDs per API list request (default: 100)",
    )
    args = parser.parse_args()

    # Validate date format
    for label, val in [("--start-date", args.start_date), ("--end-date", args.end_date)]:
        try:
            datetime.strptime(val.strip(), "%Y-%m-%d")
        except ValueError:
            print(
                f"{label} must be YYYY-MM-DD format, got: {val}",
                file=sys.stderr,
            )
            sys.exit(1)

    if args.start_date > args.end_date:
        print("--start-date must be <= --end-date", file=sys.stderr)
        sys.exit(1)

    if not ENDOR_NAMESPACE:
        print("ENDOR_NAMESPACE must be set in environment", file=sys.stderr)
        sys.exit(1)

    token = os.getenv("ENDOR_TOKEN")
    if not token:
        try:
            token = get_token()
        except Exception as e:
            print(
                "Set ENDOR_TOKEN or both API_KEY and API_SECRET in environment.",
                file=sys.stderr,
            )
            print(f"Auth failed: {e}", file=sys.stderr)
            sys.exit(1)

    headers = {
        "User-Agent": "curl/7.68.0",
        "Accept": "*/*",
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600",
    }

    filter_str = build_finding_logs_filter(
        args.start_date, args.end_date, args.project_uuid
    )
    print(f"Fetching remediated finding logs (meta.create_time {args.start_date} - {args.end_date})")
    if args.project_uuid:
        print(f"  Filtering by project: {args.project_uuid}")
    try:
        finding_logs = fetch_finding_logs(ENDOR_NAMESPACE, filter_str, headers)
    except Exception as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(finding_logs)} finding logs")

    if not finding_logs:
        write_csv_rows(args.output, [])
        print(f"Wrote 0 rows to {args.output}")
        return

    # Collect unique package_version UUIDs for enrichment
    unique_parent_uuids = list(
        {
            (obj.get("spec") or {}).get("finding_parent_uuid")
            for obj in finding_logs
            if (obj.get("spec") or {}).get("finding_parent_uuid")
        }
    )
    if unique_parent_uuids:
        print(
            f"Fetching relative_path and code_owners for {len(unique_parent_uuids)} package_version UUIDs"
        )
        try:
            package_uuid_to_relative_path, package_uuid_to_code_owners = (
                get_package_version_relative_paths_and_code_owners(
                    ENDOR_NAMESPACE,
                    unique_parent_uuids,
                    headers,
                    batch_size=args.batch_size,
                )
            )
        except Exception as e:
            print(f"Package-versions API error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        package_uuid_to_relative_path = {}
        package_uuid_to_code_owners = {}

    # Fetch CVE from vulnerabilities API for descriptions with GHSA but no CVE
    ghsa_to_cve: Dict[str, str] = {}
    for obj in finding_logs:
        desc = (obj.get("meta") or {}).get("description")
        desc_str = desc if desc is not None and str(desc).strip() else "missing"
        if extract_cve_id(desc_str):
            continue
        ghsa = extract_ghsa_id(desc_str)
        if ghsa and ghsa not in ghsa_to_cve:
            cve = fetch_cve(ghsa, headers)
            ghsa_to_cve[ghsa] = cve if cve else ""

    # Build output rows from finding logs
    out_rows: List[Dict[str, Any]] = []
    for obj in finding_logs:
        uid = obj.get("uuid") or ""
        spec = obj.get("spec") or {}
        meta = obj.get("meta") or {}
        tenant_meta = obj.get("tenant_meta") or {}

        desc = meta.get("description")
        desc_str = desc if desc is not None and str(desc).strip() else "missing"

        cve_from_desc = extract_cve_id(desc_str)
        ghsa = extract_ghsa_id(desc_str)
        if cve_from_desc:
            cve_id = cve_from_desc
        elif ghsa:
            cve_id = ghsa_to_cve.get(ghsa, "")
        else:
            cve_id = "missing"

        parent_uuid = spec.get("finding_parent_uuid") or ""
        rel_path = package_uuid_to_relative_path.get(parent_uuid, "")
        code_owners = package_uuid_to_code_owners.get(parent_uuid, "")

        out_rows.append({
            "Finding Log UUID": uid,
            "Finding UUID": spec.get("finding_uuid", ""),
            "CVE ID": cve_id,
            "Description": desc_str,
            "Criticality": spec.get("level", ""),
            "Package/Application": spec.get("finding_parent_name", ""),
            "Package Location": rel_path if rel_path else "Not Available",
            "Code Owners": code_owners if code_owners else "Not Available",
            "Introduced At": spec.get("introduced_at", ""),
            "Resolved At": spec.get("resolved_at", ""),
            "Days Unresolved": format_list_field(spec.get("days_unresolved")),
            "Tags": format_list_field(spec.get("finding_tags")),
            "Category": format_list_field(spec.get("finding_categories")),
            "Ecosystem": spec.get("ecosystem", ""),
            "Project UUID": meta.get("parent_uuid", ""),
            "Namespace": tenant_meta.get("namespace", ""),
        })

    write_csv_rows(args.output, out_rows)
    print(f"Wrote {len(out_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
