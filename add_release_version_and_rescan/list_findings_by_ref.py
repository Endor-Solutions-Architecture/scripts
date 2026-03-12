#!/usr/bin/env python3
"""
List findings for a given ref-name across all projects that match a tag.
Use after add_release_version_and_rescan to query findings on that release branch.
"""

import subprocess
import json
import sys
import argparse
import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

# Default field-mask for Finding list (vulnerability fields + dependency + remediation)
DEFAULT_FINDINGS_FIELD_MASK = (
    "spec.finding_metadata.vulnerability.spec.raw,"
    "spec.target_dependency_package_name,spec.proposed_version,spec.target_dependency_version,"
    "spec.project_uuid,spec.finding_metadata.vulnerability.spec.cvss_v3_severity,"
    "spec.remediation,spec.remediation_action,"
    "spec.finding_metadata.vulnerability.spec.cvss_v4_severity,"
    "spec.finding_metadata.vulnerability.spec.aliases"
)

# Default: critical/high, reachable (function + dependency), and normal (not test deps)
DEFAULT_FINDINGS_FILTER = (
    '(spec.level in ["FINDING_LEVEL_CRITICAL","FINDING_LEVEL_HIGH"] and '
    '(spec.finding_tags contains ["FINDING_TAGS_REACHABLE_FUNCTION"] and '
    'spec.finding_tags contains ["FINDING_TAGS_REACHABLE_DEPENDENCY"] and '
    'spec.finding_tags contains ["FINDING_TAGS_NORMAL"]))'
)


def run_endorctl_json(cmd: List[str]) -> Optional[Dict[str, Any]]:
    """Run endorctl and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running endorctl: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return None


def get_projects_by_tag(namespace: str, tag: str) -> Optional[List[Dict[str, Any]]]:
    """List projects that match the given tag."""
    cmd = [
        "endorctl", "-n", namespace,
        "api", "list", "-r", "Project",
        "--filter", f"meta.tags matches '{tag}'",
        "--field-mask", "uuid,meta.name",
    ]
    response = run_endorctl_json(cmd)
    if not response:
        return None
    return response.get("list", {}).get("objects", [])


def list_findings_for_ref(
    namespace: str,
    project_uuids: List[str],
    ref_name: str,
    findings_filter: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """List findings for the given project UUIDs on the given ref (context.id)."""
    if not project_uuids:
        return {"list": {"objects": [], "response": {}}}
    # Scope: projects + ref context
    uuid_list = "','".join(project_uuids)
    scope_expr = f"spec.project_uuid in ['{uuid_list}'] and context.type=='CONTEXT_TYPE_REF' and context.id=='{ref_name}'"
    criteria = findings_filter if findings_filter is not None else DEFAULT_FINDINGS_FILTER
    filter_expr = f"{scope_expr} and ({criteria})"
    cmd = [
        "endorctl", "-n", namespace,
        "api", "list", "-r", "Finding",
        "--filter", filter_expr,
        "--field-mask", DEFAULT_FINDINGS_FIELD_MASK,
        "--list-all",
        "--timeout", "300s",
    ]
    return run_endorctl_json(cmd)


def finding_to_csv_row(finding: Dict[str, Any]) -> Dict[str, str]:
    """Map one finding object to CSV column values."""
    spec = finding.get("spec", {})
    vuln = spec.get("finding_metadata", {}).get("vulnerability", {}).get("spec", {})
    raw = vuln.get("raw", {})
    endor = raw.get("endor_vulnerability", {})
    epss = raw.get("epss_record", {})
    cvss3 = vuln.get("cvss_v3_severity") or {}
    cvss4 = vuln.get("cvss_v4_severity") or {}

    # base_cvss: v3 score if present, else v4 base_score
    v3_score = cvss3.get("score")
    v4_score = cvss4.get("base_score")
    if v3_score is not None:
        base_cvss = str(v3_score)
        cvss_version = "3"
    elif v4_score is not None:
        base_cvss = str(v4_score)
        cvss_version = "4"
    else:
        base_cvss = ""
        cvss_version = ""

    # aliases: from vulnerability.spec.aliases (list -> comma-joined)
    aliases_list = vuln.get("aliases") or []
    aliases = ",".join(str(a) for a in aliases_list) if isinstance(aliases_list, list) else str(aliases_list)

    return {
        "cwe": str(endor.get("cwe", "")),
        "cve_id": str(endor.get("cve_id", "")),
        "aliases": aliases,
        "dependency": str(spec.get("target_dependency_package_name", "")),
        "project": str(spec.get("project_uuid", "")),
        "fix_available": str(spec.get("proposed_version", "")),
        "affected_versions": str(spec.get("target_dependency_version", "")),
        "epss_score": str(epss.get("probability", "")),
        "base_cvss": base_cvss,
        "cvss_version": cvss_version,
        "remediation": str(spec.get("remediation", "")),
        "remediation_action": str(spec.get("remediation_action", "")),
    }


def sanitize_filename_part(s: str) -> str:
    """Replace chars unsafe for filenames with underscore."""
    return re.sub(r'[/\\:*?"<>|\s]+', "_", s).strip("_") or "findings"


def write_findings_csv(objects: List[Dict[str, Any]], tag: str, ref_name: str) -> str:
    """Write findings to a CSV file; return the file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_tag = sanitize_filename_part(tag)
    safe_ref = sanitize_filename_part(ref_name)
    filename = f"findings_{safe_tag}_{safe_ref}_{timestamp}.csv"

    fieldnames = [
        "cwe", "cve_id", "aliases", "dependency", "project", "fix_available",
        "affected_versions", "epss_score", "base_cvss", "cvss_version",
        "remediation", "remediation_action",
    ]
    rows = [finding_to_csv_row(obj) for obj in objects]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List findings for a ref-name across all projects matching a tag.",
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace (tenant)")
    parser.add_argument("--tag", required=True, help="Project tag to match (e.g. my-product)")
    parser.add_argument("--ref-name", required=True, help="Ref/version to query (e.g. release/1.1.1)")
    parser.add_argument(
        "--filter",
        dest="findings_filter",
        metavar="EXPR",
        default=None,
        help="Optional filter expression for findings. If omitted, uses default: critical/high, reachable, normal (not test deps).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only raw JSON to stdout (no summary to stderr)",
    )
    args = parser.parse_args()

    namespace = args.namespace
    tag = args.tag
    ref_name = args.ref_name
    findings_filter = args.findings_filter

    if not args.json:
        print("List findings by ref", file=sys.stderr)
        print(f"  Namespace: {namespace}", file=sys.stderr)
        print(f"  Tag:       {tag}", file=sys.stderr)
        print(f"  Ref name:  {ref_name}", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

    try:
        subprocess.run(
            ["endorctl", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.", file=sys.stderr)
        sys.exit(1)

    projects = get_projects_by_tag(namespace, tag)
    if projects is None:
        sys.exit(1)
    if not projects:
        if not args.json:
            print("No projects found matching the given tag.", file=sys.stderr)
        print(json.dumps({"list": {"objects": [], "response": {}}}))
        return

    project_uuids = [p.get("uuid", "") for p in projects if p.get("uuid")]
    if not args.json:
        print(f"Found {len(project_uuids)} project(s). Querying findings for ref '{ref_name}'...", file=sys.stderr)
        if findings_filter is not None:
            print("Using custom --filter expression.", file=sys.stderr)
        else:
            print("Using default filter (critical/high, reachable, normal).", file=sys.stderr)

    response = list_findings_for_ref(namespace, project_uuids, ref_name, findings_filter)
    if response is None:
        sys.exit(1)

    objects = response.get("list", {}).get("objects", [])
    if not args.json:
        print(f"Findings for ref '{ref_name}': {len(objects)}", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

    # Always write CSV with dynamic name + timestamp
    csv_path = write_findings_csv(objects, tag, ref_name)
    if not args.json:
        print(f"CSV written to: {csv_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
