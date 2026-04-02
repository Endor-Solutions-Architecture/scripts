#!/usr/bin/env python3
"""
PR Block/Warn Report Generator - CLI

Generates a CSV report of PR scans that triggered action policy enforcement
(block or warn) across a namespace. Uses endorctl to query ScanResult and
Project resources.
"""

import subprocess
import json
import csv
import sys
import argparse
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional


UI_BASE = "https://app.endorlabs.com"


def run_endorctl(args: List[str], namespace: str, timeout: int = 120) -> Optional[Dict[str, Any]]:
    """Execute an endorctl command and return parsed JSON."""
    cmd = ["endorctl", "-n", namespace] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error executing: {' '.join(cmd)}")
        print(f"stderr: {e.stderr}")
        return None
    except subprocess.TimeoutExpired:
        print(f"Timeout executing: {' '.join(cmd)}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def get_enforced_scan_results(namespace: str, days: int) -> List[Dict[str, Any]]:
    """Fetch ScanResults that have blocking or warning findings."""
    print(f"Fetching ScanResults with block/warn findings (last {days} days)...")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    filter_expr = (
        "(spec.blocking_findings exists or spec.warning_findings exists)"
        ' and context.type == "CONTEXT_TYPE_CI_RUN"'
        f' and meta.create_time > date("{cutoff}")'
    )

    response = run_endorctl(
        [
            "api", "list", "-r", "ScanResult",
            "--filter", filter_expr,
            "--field-mask", (
                "uuid,"
                "meta.create_time,"
                "meta.parent_uuid,"
                "meta.tags,"
                "tenant_meta.namespace,"
                "context.tags,"
                "spec.status,"
                "spec.blocking_findings,"
                "spec.warning_findings"
            ),
            "--sort-path", "meta.create_time",
            "--sort-order", "descending",
            "--list-all",
            "-t", "300s",
        ],
        namespace,
        timeout=360,
    )

    if not response:
        return []

    objects = response.get("list", {}).get("objects", [])
    print(f"Found {len(objects)} ScanResults with block/warn findings")
    return objects


def extract_pr_number(scan_result: Dict[str, Any]) -> Optional[str]:
    """Extract PR number from context.tags or meta.tags (e.g. 'pr=1')."""
    for tag_source in [scan_result.get("context", {}).get("tags", []),
                       scan_result.get("meta", {}).get("tags", [])]:
        for tag in tag_source:
            if tag.startswith("pr="):
                return tag.split("=", 1)[1]
    return None


def get_project_info(namespace: str, project_uuids: List[str]) -> Dict[str, Dict[str, str]]:
    """Resolve project UUIDs to full_name and http_clone_url."""
    if not project_uuids:
        return {}

    print(f"Resolving info for {len(project_uuids)} projects...")
    uuid_list = "', '".join(project_uuids)
    response = run_endorctl(
        [
            "api", "list", "-r", "Project",
            "--filter", f"uuid in ['{uuid_list}']",
            "--field-mask", "uuid,spec.git.full_name,spec.git.http_clone_url",
            "--list-all",
        ],
        namespace,
        timeout=120,
    )

    if not response:
        return {}

    projects = {}
    for obj in response.get("list", {}).get("objects", []):
        git = obj.get("spec", {}).get("git", {})
        clone_url = git.get("http_clone_url", "")
        # Strip .git suffix for clean PR URLs
        base_url = clone_url.rstrip("/").removesuffix(".git") if clone_url else ""
        projects[obj.get("uuid", "")] = {
            "full_name": git.get("full_name", "Unknown"),
            "base_url": base_url,
        }

    return projects


def build_pr_url(base_url: str, pr_number: Optional[str]) -> str:
    """Construct PR URL from project base URL and PR number."""
    if not base_url or not pr_number:
        return "N/A"
    return f"{base_url}/pull/{pr_number}"


def generate_report(namespace: str, days: int) -> None:
    """Main report generation logic."""
    # Step 1: Get ScanResults with block/warn (small, targeted query)
    scan_results = get_enforced_scan_results(namespace, days)
    if not scan_results:
        print("No ScanResults with block/warn findings found.")
        return

    # Step 2: Collect project UUIDs and resolve in bulk
    project_uuids = list(set(
        sr.get("meta", {}).get("parent_uuid", "")
        for sr in scan_results
        if sr.get("meta", {}).get("parent_uuid")
    ))
    project_info = get_project_info(namespace, project_uuids)

    # Step 3: Build report rows
    rows = []
    for sr in scan_results:
        sr_uuid = sr.get("uuid", "")
        meta = sr.get("meta", {})
        spec = sr.get("spec", {})
        ns = sr.get("tenant_meta", {}).get("namespace", namespace)
        project_uuid = meta.get("parent_uuid", "")
        proj = project_info.get(project_uuid, {"full_name": "Unknown", "base_url": ""})

        blocking = spec.get("blocking_findings", [])
        warning = spec.get("warning_findings", [])
        outcome = "block" if blocking else "warn"

        pr_number = extract_pr_number(sr)

        rows.append({
            "date": meta.get("create_time", ""),
            "project_name": proj["full_name"],
            "project_url": f"{UI_BASE}/t/{ns}/projects/{project_uuid}",
            "pr_url": build_pr_url(proj["base_url"], pr_number),
            "scan_result_url": f"{UI_BASE}/t/{ns}/scan-history/{sr_uuid}",
            "outcome": outcome,
            "blocker_findings": len(blocking),
            "warning_findings": len(warning),
            "pr_check_conclusion": spec.get("status", ""),
        })

    # Write CSV
    os.makedirs("generated_reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_reports/pr_block_warn_{namespace}_{timestamp}.csv"

    fieldnames = [
        "date", "project_name", "project_url", "pr_url", "scan_result_url",
        "outcome", "blocker_findings", "warning_findings", "pr_check_conclusion",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nReport generated: {filename}")
    print(f"Total PR scans with block/warn: {len(rows)}")
    print(f"  Blocked: {sum(1 for r in rows if r['outcome'] == 'block')}")
    print(f"  Warned:  {sum(1 for r in rows if r['outcome'] == 'warn')}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a report of PR scans that were blocked or warned by action policies"
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace/tenant to query")
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to look back (default: 30)"
    )
    args = parser.parse_args()

    print(f"PR Block/Warn Report")
    print(f"Namespace: {args.namespace}")
    print(f"Lookback:  {args.days} days")
    print("-" * 50)

    # Check endorctl availability
    try:
        subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.")
        sys.exit(1)

    generate_report(args.namespace, args.days)
    print("\nDone!")


if __name__ == "__main__":
    main()
