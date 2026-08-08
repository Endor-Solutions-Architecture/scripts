#!/usr/bin/env python3
"""
WHAT IT DOES:
- Adds CWE column to the SAST export via API, since the platform export doesn't include CWE yet.
- This is a TEMPORARY SOLUTION until the platform export includes the CWE column for SAST findings.
- The script uses the SAST-specific metadata that the UI export doesn't expose. 
"""
import argparse
import csv
import json
import subprocess
import sys
from typing import Dict, List, Any

def run_endorctl_api_list(args: List[str]) -> Dict[str, Any]:
    """Call `endorctl api list` and return parsed JSON."""
    cmd = ["endorctl", "api", "list"] + args
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)

def get_projects_with_namespaces(root_namespace: str) -> List[Dict[str, str]]:
    """
    List all projects in root namespace AND child namespaces.
    Uses --traverse on Project.
    """
    args = [
        "--namespace",
        root_namespace,
        "--resource",
        "Project",
        "--traverse",
        "--list-all",
        "--field-mask",
        "uuid,meta.name,tenant_meta",
    ]
    data = run_endorctl_api_list(args)
    projects = []
    for obj in data.get("list", {}).get("objects", []):
        projects.append(
            {
                "uuid": obj["uuid"],
                "name": obj["meta"]["name"],
                "namespace": obj["tenant_meta"]["namespace"],
            }
        )
    return projects

def get_sast_findings_for_project(project: Dict[str, str]) -> List[Dict[str, Any]]:
    """Return all non-exception SAST findings for a single project UUID."""
    proj_uuid = project["uuid"]
    filter_expr = (
        'context.type == "CONTEXT_TYPE_MAIN" '
        f'and spec.project_uuid=="{proj_uuid}" '
        'and spec.finding_categories contains ["FINDING_CATEGORY_SAST"] '
        'and spec.finding_tags not contains ["FINDING_TAGS_EXCEPTION"]'
    )

    field_mask = ",".join(
        [
            "uuid",
            "meta.description",
            "spec.level",
            "spec.finding_tags",
            "spec.finding_categories",
            "spec.remediation",
            "spec.finding_metadata.custom",
        ]
    )

    args = [
        "--namespace",
        project["namespace"],
        "--resource",
        "Finding",
        "--filter",
        filter_expr,
        "--field-mask",
        field_mask,
        "--list-all",
    ]

    data = run_endorctl_api_list(args)
    return data.get("list", {}).get("objects", [])

def build_csv_row(finding: Dict[str, Any], project_name: str) -> Dict[str, str]:
    """
    Map a Finding object into UI-equivalent CSV columns:
    UUID, Title, Severity Level, Attributes, Finding Categories,
    Remediation, Fix Version, Risk Details, Explanation, CVE, CWE, Project Name
    """
    uuid = finding.get("uuid", "")
    meta = finding.get("meta", {}) or {}
    spec = finding.get("spec", {}) or {}

    fm = spec.get("finding_metadata", {}) or {}
    custom = fm.get("custom", {}) or {}

    title = meta.get("description") or custom.get("message") or ""
    severity = spec.get("level", "")
    attributes = ",".join(spec.get("finding_tags", []) or [])
    categories = ",".join(spec.get("finding_categories", []) or [])
    remediation = spec.get("remediation", "") or ""

    fix_version = ""  # no fix version for SAST
    cve = ""          # no CVE for SAST

    risk_details = "A SAST finding was identified in this repository version."
    explanation = custom.get("explanation", "")

    cwes = custom.get("cwes", []) or []
    cwe_str = ";".join(cwes)

    return {
        "UUID": uuid,
        "Title": title,
        "Severity Level": severity,
        "Attributes": attributes,
        "Finding Categories": categories,
        "Remediation": remediation,
        "Fix Version": fix_version,
        "Risk Details": risk_details,
        "Explanation": explanation,
        "CVE": cve,
        "CWE": cwe_str,
        "Project Name": project_name,
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export all SAST findings (including child namespaces) for a root "
            "namespace into a CSV, with CWE populated from SAST rule metadata."
        )
    )
    parser.add_argument(
        "-n",
        "--namespace",
        required=True,
        help="Root namespace to traverse (e.g. rubrik.prod)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output CSV file path (e.g. sast-findings-with-cwe.csv)",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    root_namespace = args.namespace
    output_csv = args.output

    print(f"Enumerating projects under namespace '{root_namespace}' (including children)...")
    projects = get_projects_with_namespaces(root_namespace)
    print(f"Found {len(projects)} projects")

    fieldnames = [
        "UUID",
        "Title",
        "Severity Level",
        "Attributes",
        "Finding Categories",
        "Remediation",
        "Fix Version",
        "Risk Details",
        "Explanation",
        "CVE",
        "CWE",
        "Project Name",
    ]

    total_findings = 0
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for proj in projects:
            pname = proj["name"]
            print(f"Fetching SAST findings for project '{pname}' in namespace '{proj['namespace']}'...")
            findings = get_sast_findings_for_project(proj)
            for finding in findings:
                row = build_csv_row(finding, pname)
                writer.writerow(row)
                total_findings += 1

    print(f"Done. Wrote {total_findings} SAST findings to {output_csv}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("endorctl command failed:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)
