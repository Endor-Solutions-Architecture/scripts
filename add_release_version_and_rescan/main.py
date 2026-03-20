#!/usr/bin/env python3
"""
Add a repository version (ref-name) to all projects matching a tag and trigger a full rescan.
Uses endorctl to list projects by tag, create RepositoryVersion for each, then request rescan.
"""

import subprocess
import json
import sys
import argparse
from typing import List, Dict, Any, Optional


def run_endorctl_list(namespace: str, tag: str) -> Optional[Dict[str, Any]]:
    """List projects that match the given tag. Returns parsed JSON or None on failure."""
    cmd = [
        "endorctl", "-n", namespace,
        "api", "list", "-r", "Project",
        "--filter", f"meta.tags matches '{tag}'",
        "--field-mask", "uuid,meta.name",
    ]
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
        print(f"Error listing projects: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing list response: {e}", file=sys.stderr)
        return None


def add_repository_version(namespace: str, project_uuid: str, ref_name: str) -> bool:
    """Create a RepositoryVersion for the project. Returns True on success."""
    payload = {
        "meta": {"name": ref_name, "parent_uuid": project_uuid},
        "context": {"id": ref_name, "type": "CONTEXT_TYPE_REF"},
        "spec": {"version": {"ref": ref_name}},
    }
    cmd = [
        "endorctl", "-n", namespace,
        "api", "create", "-r", "RepositoryVersion",
        "--data", json.dumps(payload),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error adding version: {e.stderr}", file=sys.stderr)
        return False


def trigger_rescan(namespace: str, project_uuid: str) -> bool:
    """Request a full rescan for the project. Returns True on success."""
    payload = {
        "processing_status": {
            "scan_state": "SCAN_STATE_REQUEST_FULL_RESCAN",
            "analytic_time": "1984-01-01T00:00:00.000000000Z",
        }
    }
    cmd = [
        "endorctl", "api", "update", "-r", "Project", "-n", namespace,
        "--uuid", project_uuid,
        "--field-mask", "processing_status.scan_state,processing_status.analytic_time",
        "--data", json.dumps(payload),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error triggering rescan: {e.stderr}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a repository version (ref-name) to all projects matching a tag and trigger a full rescan.",
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace (tenant)")
    parser.add_argument("--tag", required=True, help="Project tag to match (e.g. my-product)")
    parser.add_argument("--ref-name", required=True, help="Ref name / version to add (e.g. release/1.0.0 or v1.0.0)")
    args = parser.parse_args()

    namespace = args.namespace
    tag = args.tag
    ref_name = args.ref_name

    print("Add release version and rescan")
    print(f"  Namespace: {namespace}")
    print(f"  Tag:       {tag}")
    print(f"  Ref name:  {ref_name}")
    print("-" * 50)

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

    response = run_endorctl_list(namespace, tag)
    if not response:
        sys.exit(1)

    objects = response.get("list", {}).get("objects", [])
    if not objects:
        print("No projects found matching the given tag.")
        return

    print(f"Found {len(objects)} project(s) matching tag '{tag}'.\n")

    success_count = 0
    for project in objects:
        project_uuid = project.get("uuid", "")
        project_name = project.get("meta", {}).get("name", "Unknown")

        print(f"Updating project {project_name}")

        if not add_repository_version(namespace, project_uuid, ref_name):
            print(f"  Skipping rescan for {project_name} (add version failed).")
            continue

        print(f"Triggering rescan for project {project_name}")
        if trigger_rescan(namespace, project_uuid):
            success_count += 1
        else:
            print(f"  Rescan requested but API reported an error for {project_name}.")

    print("-" * 50)
    print(f"Done. Successfully added version '{ref_name}' and triggered rescan for {success_count}/{len(objects)} project(s).")


if __name__ == "__main__":
    main()
