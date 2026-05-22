#!/usr/bin/env python3
"""
Generate a findings report from the Findings API.

Fetches findings (Vulnerabilities, Secrets, SAST, Container, License,
Operational, Malware) via the Findings list API, enriches with
PackageVersion (relative_path, code_owners) and Projects (project name),
and writes a CSV report. All CVE/CWE/CVSS/EPSS data comes directly from
the Findings API—no separate Vulnerabilities API call is needed.

Usage:
    python generate_findings_report.py --end-date 2026-01-31 --output report.csv
    python generate_findings_report.py --end-date 2026-01-31 --output report.csv --project-uuid xxxxxxxxxxxxxxxx
    python generate_findings_report.py --end-date 2026-01-31 --output report.csv --split-by-category
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

CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+")

FINDINGS_MASK = (
    "uuid,meta.create_time,meta.description,meta.parent_uuid,meta.parent_kind,"
    "spec.project_uuid,spec.level,spec.remediation,spec.finding_metadata,"
    "spec.finding_tags,spec.finding_categories,spec.ecosystem,"
    "spec.target_dependency_package_name,spec.target_dependency_name,"
    "spec.target_dependency_version,spec.dependency_file_paths,"
    "tenant_meta.namespace"
)
PACKAGE_VERSIONS_MASK = "uuid,spec.relative_path,spec.code_owners.owners"
PROJECTS_MASK = "uuid,meta.name"

OUTPUT_COLUMNS = [
    "Finding UUID",
    "Category",
    "CVE ID",
    "CWE ID",
    "Description",
    "Criticality",
    "Remediation",
    "Package/Application",
    "Package Location",
    "Code Owners",
    "Location File",
    "Introduced At",
    "Tags",
    "Ecosystem",
    "Project UUID",
    "Project Name",
    "Reachability",
    "Fixable",
    "CVSS Score",
    "EPSS Score",
    "Namespace",
]

_ECOSYSTEM_DISPLAY_MAP = {
    "ECOSYSTEM_APK": "APK",
    "ECOSYSTEM_C": "C/C++",
    "ECOSYSTEM_CARGO": "Rust",
    "ECOSYSTEM_COCOAPOD": "CocoaPods",
    "ECOSYSTEM_DEBIAN": "Debian",
    "ECOSYSTEM_GEM": "Ruby",
    "ECOSYSTEM_GO": "Go",
    "ECOSYSTEM_MAVEN": "Java",
    "ECOSYSTEM_NPM": "JavaScript",
    "ECOSYSTEM_NUGET": ".NET",
    "ECOSYSTEM_PACKAGIST": "PHP",
    "ECOSYSTEM_PYPI": "Python",
    "ECOSYSTEM_RPM": "RPM",
    "ECOSYSTEM_SWIFT": "Swift",
}

_LEVEL_DISPLAY_MAP = {
    "FINDING_LEVEL_CRITICAL": "Critical",
    "FINDING_LEVEL_HIGH": "High",
    "FINDING_LEVEL_MEDIUM": "Medium",
    "FINDING_LEVEL_LOW": "Low",
    "FINDING_LEVEL_INFO": "Info",
    "FINDING_LEVEL_UNSPECIFIED": "",
}

_CATEGORY_PRIORITY = [
    ("FINDING_CATEGORY_CONTAINER", "Container"),
    ("FINDING_CATEGORY_SAST", "SAST"),
    ("FINDING_CATEGORY_SECRETS", "Secrets"),
    ("FINDING_CATEGORY_MALWARE", "Malware"),
    ("FINDING_CATEGORY_LICENSE_RISK", "License"),
    ("FINDING_CATEGORY_OPERATIONAL", "Operational"),
    ("FINDING_CATEGORY_VULNERABILITY", "Vulnerability"),
]

_REACHABILITY_TAG_MAP = {
    "FINDING_TAGS_REACHABLE_FUNCTION": "Reachable",
    "FINDING_TAGS_UNREACHABLE_FUNCTION": "Unreachable",
    "FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION": "Potentially Reachable",
}

_VULN_CONTAINER_CATEGORIES = {"Vulnerability", "Container"}

ALL_CATEGORY_LABELS = [label for _, label in _CATEGORY_PRIORITY]


def friendly_ecosystem(raw: str) -> str:
    """Map raw ecosystem enum to a human-readable name."""
    if not raw:
        return ""
    label = _ECOSYSTEM_DISPLAY_MAP.get(raw)
    if label:
        return label
    return raw.replace("ECOSYSTEM_", "").replace("_", " ").title()


def friendly_level(raw: str) -> str:
    """Map raw finding level enum to a human-readable name."""
    if not raw:
        return ""
    label = _LEVEL_DISPLAY_MAP.get(raw)
    if label is not None:
        return label
    return raw.replace("FINDING_LEVEL_", "").replace("_", " ").title()


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


def parse_date_to_iso(date_str: str) -> str:
    """Parse YYYY-MM-DD to end-of-day ISO 8601 string for API filter."""
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_findings_filter(
    end_date: str,
    project_uuid: Optional[str] = None,
) -> str:
    """Build filter for findings up to end_date."""
    end_iso = parse_date_to_iso(end_date)
    filters = [
        "context.type==CONTEXT_TYPE_MAIN",
        f"meta.create_time <= date({end_iso})",
    ]
    if project_uuid:
        filters.append(f'spec.project_uuid=="{project_uuid}"')
    return " and ".join(filters)


def fetch_findings(
    namespace: str,
    filter_str: str,
    headers: Dict[str, str],
    page_size: int = 500,
) -> List[Dict[str, Any]]:
    """Fetch all findings matching the filter; paginate through results."""
    url = f"{API_URL}/namespaces/{namespace}/findings"
    objects: List[Dict[str, Any]] = []
    next_page_id = None
    while True:
        params = {
            "list_parameters.filter": filter_str,
            "list_parameters.mask": FINDINGS_MASK,
            "list_parameters.page_size": str(page_size),
        }
        if next_page_id is not None:
            params["list_parameters.page_id"] = next_page_id
        response = requests.get(url, headers=headers, params=params, timeout=600)
        if response.status_code != 200:
            print(
                f"Findings API error: {response.status_code} - {response.text}",
                file=sys.stderr,
            )
            raise RuntimeError(f"Findings API failed: {response.status_code}")
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
    Fetch package-versions by uuid; return (uuid -> spec.relative_path,
    uuid -> code_owners string).
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


def get_project_names(
    namespace: str,
    project_uuids: List[str],
    headers: Dict[str, str],
    batch_size: int = 100,
) -> Dict[str, str]:
    """Fetch projects by uuid; return uuid -> meta.name map."""
    names: Dict[str, str] = {}
    if not project_uuids:
        return names
    url = f"{API_URL}/namespaces/{namespace}/projects"
    for i in range(0, len(project_uuids), batch_size):
        batch = project_uuids[i : i + batch_size]
        uuid_list = "', '".join(batch)
        filter_str = f"uuid in ['{uuid_list}']"
        next_page_id = None
        while True:
            params = {
                "list_parameters.filter": filter_str,
                "list_parameters.mask": PROJECTS_MASK,
                "list_parameters.page_size": "500",
            }
            if next_page_id is not None:
                params["list_parameters.page_id"] = next_page_id
            response = requests.get(url, headers=headers, params=params, timeout=600)
            if response.status_code != 200:
                print(
                    f"Projects API error: {response.status_code} - {response.text}",
                    file=sys.stderr,
                )
                raise RuntimeError(f"Projects API failed: {response.status_code}")
            data = response.json()
            objs = data.get("list", {}).get("objects", [])
            for obj in objs:
                uid = obj.get("uuid")
                if not uid:
                    continue
                name = (obj.get("meta") or {}).get("name") or ""
                names[uid] = name.strip() if isinstance(name, str) else str(name)
            next_page_id = data.get("list", {}).get("response", {}).get("next_page_id")
            if not next_page_id:
                break
    return names


def derive_category(finding_categories: Any) -> str:
    """Map finding_categories list to a single clean label using priority."""
    if not finding_categories:
        return "Other"
    cats = finding_categories if isinstance(finding_categories, list) else [finding_categories]
    cat_set = set(cats)
    for raw_cat, label in _CATEGORY_PRIORITY:
        if raw_cat in cat_set:
            return label
    return "Other"


def derive_fixable(finding_tags: Any) -> str:
    """Return Yes/No fixability label from finding_tags."""
    if not finding_tags:
        return ""
    tags = finding_tags if isinstance(finding_tags, list) else [finding_tags]
    if "FINDING_TAGS_FIX_AVAILABLE" in tags:
        return "Yes"
    if "FINDING_TAGS_UNFIXABLE" in tags:
        return "No"
    return ""


def derive_reachability(finding_tags: Any) -> str:
    """Return a human-readable reachability label from finding_tags."""
    if not finding_tags:
        return ""
    tags = finding_tags if isinstance(finding_tags, list) else [finding_tags]
    for tag in tags:
        label = _REACHABILITY_TAG_MAP.get(tag)
        if label:
            return label
    return ""


def format_list_field(val: Any) -> str:
    """Format list/array field for CSV output."""
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return str(val)


def extract_cve_from_finding(obj: Dict[str, Any]) -> str:
    """
    Extract CVE ID from finding metadata. Checks vulnerability aliases first,
    then vulnerability meta.name, then falls back to regex on meta.description.
    """
    spec = obj.get("spec") or {}
    fm = spec.get("finding_metadata") or {}

    vuln = fm.get("vulnerability")
    if vuln:
        vuln_spec = vuln.get("spec") or {}
        aliases = vuln_spec.get("aliases") or []
        for alias in aliases:
            if isinstance(alias, str) and alias.startswith("CVE-"):
                return alias
        vuln_meta = vuln.get("meta") or {}
        vuln_name = vuln_meta.get("name") or ""
        if vuln_name.startswith("CVE-"):
            return vuln_name

    desc = (obj.get("meta") or {}).get("description") or ""
    match = CVE_PATTERN.search(desc)
    if match:
        return match.group(0)

    return ""


def extract_cwe_from_finding(obj: Dict[str, Any], category: str) -> str:
    """
    Extract CWE IDs from finding based on category.
    - SAST: spec.finding_metadata.custom.cwes
    - Vulnerability/Container: spec.finding_metadata.vulnerability.spec.database_specific.cwe_ids
    - Malware: spec.finding_metadata.malware.spec.cwe_id
    """
    spec = obj.get("spec") or {}
    fm = spec.get("finding_metadata") or {}

    if category == "SAST":
        custom = fm.get("custom") or {}
        cwes = custom.get("cwes")
        if cwes:
            return ", ".join(str(c) for c in cwes) if isinstance(cwes, list) else str(cwes)

    if category in ("Vulnerability", "Container"):
        vuln = fm.get("vulnerability") or {}
        vuln_spec = vuln.get("spec") or {}
        db_specific = vuln_spec.get("database_specific") or {}
        cwe_ids = db_specific.get("cwe_ids")
        if cwe_ids:
            return ", ".join(str(c) for c in cwe_ids) if isinstance(cwe_ids, list) else str(cwe_ids)

    if category == "Malware":
        malware = fm.get("malware") or {}
        malware_spec = malware.get("spec") or {}
        cwe_id = malware_spec.get("cwe_id")
        if cwe_id:
            return str(cwe_id)

    return ""


def derive_package_application(obj: Dict[str, Any]) -> str:
    """Derive Package/Application from finding fields."""
    spec = obj.get("spec") or {}
    pkg_name = spec.get("target_dependency_package_name")
    if pkg_name:
        return str(pkg_name)

    fm = spec.get("finding_metadata") or {}
    spi = fm.get("source_policy_info") or {}
    finding_name = spi.get("finding_name")
    if finding_name:
        return str(finding_name)

    desc = (obj.get("meta") or {}).get("description") or ""
    return desc


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
        description="Generate findings report from Findings API."
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="Report end date (YYYY-MM-DD). Findings with meta.create_time <= end of this date.",
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
        help="Number of UUIDs per API batch request for PackageVersions and Projects (default: 100).",
    )
    parser.add_argument(
        "--split-by-category",
        action="store_true",
        default=False,
        help="Write separate CSV files per finding category instead of a single combined file.",
    )
    args = parser.parse_args()

    for label, val in [("--end-date", args.end_date)]:
        try:
            datetime.strptime(val.strip(), "%Y-%m-%d")
        except ValueError:
            print(f"{label} must be YYYY-MM-DD format, got: {val}", file=sys.stderr)
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

    filter_str = build_findings_filter(args.end_date, args.project_uuid)
    print(f"Fetching findings (meta.create_time <= {args.end_date})")
    if args.project_uuid:
        print(f"  Filtering by project: {args.project_uuid}")
    try:
        findings = fetch_findings(ENDOR_NAMESPACE, filter_str, headers)
    except Exception as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(findings)} findings")

    if not findings:
        write_csv_rows(args.output, [])
        print(f"Wrote 0 rows to {args.output}")
        return

    # --- Enrichment: PackageVersions ---
    pv_uuids = list(
        {
            (obj.get("meta") or {}).get("parent_uuid")
            for obj in findings
            if (obj.get("meta") or {}).get("parent_kind") == "PackageVersion"
            and (obj.get("meta") or {}).get("parent_uuid")
        }
    )
    if pv_uuids:
        print(f"Fetching relative_path and code_owners for {len(pv_uuids)} package_version UUIDs")
        try:
            pv_to_path, pv_to_owners = get_package_version_relative_paths_and_code_owners(
                ENDOR_NAMESPACE, pv_uuids, headers, batch_size=args.batch_size
            )
        except Exception as e:
            print(f"Package-versions API error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        pv_to_path = {}
        pv_to_owners = {}

    # --- Enrichment: Projects ---
    project_uuids = list(
        {
            (obj.get("spec") or {}).get("project_uuid")
            for obj in findings
            if (obj.get("spec") or {}).get("project_uuid")
        }
    )
    if project_uuids:
        print(f"Fetching project names for {len(project_uuids)} project UUIDs")
        try:
            project_names = get_project_names(
                ENDOR_NAMESPACE, project_uuids, headers, batch_size=args.batch_size
            )
        except Exception as e:
            print(f"Projects API error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        project_names = {}

    # --- Build output rows ---
    out_rows: List[Dict[str, Any]] = []
    for obj in findings:
        uid = obj.get("uuid") or ""
        spec = obj.get("spec") or {}
        meta = obj.get("meta") or {}
        tenant_meta = obj.get("tenant_meta") or {}

        finding_categories = spec.get("finding_categories")
        category = derive_category(finding_categories)
        finding_tags = spec.get("finding_tags")

        parent_uuid = meta.get("parent_uuid") or ""
        parent_kind = meta.get("parent_kind") or ""

        rel_path = ""
        code_owners = ""
        if parent_kind == "PackageVersion" and parent_uuid:
            rel_path = pv_to_path.get(parent_uuid, "")
            code_owners = pv_to_owners.get(parent_uuid, "")

        proj_uuid = spec.get("project_uuid") or ""
        proj_name = project_names.get(proj_uuid, "")

        reachability = ""
        if category in _VULN_CONTAINER_CATEGORIES:
            reachability = derive_reachability(finding_tags)

        cve_id = ""
        cvss_score = ""
        epss_score = ""
        if category in _VULN_CONTAINER_CATEGORIES:
            cve_id = extract_cve_from_finding(obj)
            fm = spec.get("finding_metadata") or {}
            vuln = fm.get("vulnerability") or {}
            vuln_spec = vuln.get("spec") or {}
            cvss_sev = vuln_spec.get("cvss_v3_severity") or {}
            score = cvss_sev.get("score")
            if score is not None:
                cvss_score = str(score)
            epss = vuln_spec.get("epss_score") or {}
            prob = epss.get("probability_score")
            if prob is not None:
                epss_score = str(prob)

        cwe_id = extract_cwe_from_finding(obj, category)

        dep_file_paths = spec.get("dependency_file_paths")
        location_file = format_list_field(dep_file_paths) if dep_file_paths else ""

        desc = meta.get("description") or ""

        out_rows.append({
            "Finding UUID": uid,
            "Category": category,
            "CVE ID": cve_id,
            "CWE ID": cwe_id,
            "Description": desc,
            "Criticality": friendly_level(spec.get("level", "")),
            "Remediation": spec.get("remediation", ""),
            "Package/Application": derive_package_application(obj),
            "Package Location": rel_path if rel_path else "Not Available",
            "Code Owners": code_owners if code_owners else "Not Available",
            "Location File": location_file,
            "Introduced At": meta.get("create_time", ""),
            "Tags": format_list_field(finding_tags),
            "Ecosystem": friendly_ecosystem(spec.get("ecosystem", "")),
            "Project UUID": proj_uuid,
            "Project Name": proj_name if proj_name else "Not Available",
            "Reachability": reachability,
            "Fixable": derive_fixable(finding_tags),
            "CVSS Score": cvss_score,
            "EPSS Score": epss_score,
            "Namespace": tenant_meta.get("namespace", ""),
        })

    if args.split_by_category:
        base, ext = os.path.splitext(args.output)
        if not ext:
            ext = ".csv"
        rows_by_cat: Dict[str, List[Dict[str, Any]]] = {
            label: [] for label in ALL_CATEGORY_LABELS
        }
        rows_by_cat["Other"] = []
        for row in out_rows:
            rows_by_cat.setdefault(row["Category"], []).append(row)

        total_files = 0
        for cat_label, cat_rows in rows_by_cat.items():
            if not cat_rows:
                continue
            cat_slug = cat_label.lower().replace(" ", "_")
            cat_path = f"{base}_{cat_slug}{ext}"
            write_csv_rows(cat_path, cat_rows)
            print(f"  {cat_label}: {len(cat_rows)} rows -> {cat_path}")
            total_files += 1
        print(f"Wrote {len(out_rows)} total rows across {total_files} files")
    else:
        write_csv_rows(args.output, out_rows)
        print(f"Wrote {len(out_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
