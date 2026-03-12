#!/usr/bin/env python3
"""
List findings for a given ref-name across all projects that match a tag.
Use after add_release_version_and_rescan to query findings on that release branch.
"""

import subprocess
import json
import sys
import argparse
from typing import List, Dict, Any, Optional


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
) -> Optional[Dict[str, Any]]:
    """List findings for the given project UUIDs on the given ref (context.id)."""
    if not project_uuids:
        return {"list": {"objects": [], "response": {}}}
    # Filter: spec.project_uuid in ['uuid1','uuid2',...] and context.type=='CONTEXT_TYPE_REF' and context.id=='<ref-name>'
    uuid_list = "','".join(project_uuids)
    filter_expr = f"spec.project_uuid in ['{uuid_list}'] and context.type=='CONTEXT_TYPE_REF' and context.id=='{ref_name}'"
    cmd = [
        "endorctl", "-n", namespace,
        "api", "list", "-r", "Finding",
        "--filter", filter_expr,
        "--list-all",
        "--timeout", "300s",
    ]
    return run_endorctl_json(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List findings for a ref-name across all projects matching a tag.",
    )
    parser.add_argument("-n", "--namespace", required=True, help="Namespace (tenant)")
    parser.add_argument("--tag", required=True, help="Project tag to match (e.g. my-product)")
    parser.add_argument("--ref-name", required=True, help="Ref/version to query (e.g. release/1.1.1)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only raw JSON to stdout (no summary to stderr)",
    )
    args = parser.parse_args()

    namespace = args.namespace
    tag = args.tag
    ref_name = args.ref_name

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

    response = list_findings_for_ref(namespace, project_uuids, ref_name)
    if response is None:
        sys.exit(1)

    objects = response.get("list", {}).get("objects", [])
    if not args.json:
        print(f"Findings for ref '{ref_name}': {len(objects)}", file=sys.stderr)
        print("-" * 50, file=sys.stderr)

    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
