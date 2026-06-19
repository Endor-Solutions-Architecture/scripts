#!/usr/bin/env python3
"""
Tag dependencies in an Endor Labs project.

Reads a text file containing dependency names and versions (one per line in
``name@version`` format) and applies one or more tags to the matching
DependencyMetadata records for a given project.
"""

import argparse
import json
import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()

API_URL = "https://api.endorlabs.com/v1"


def get_env_values():
    """Load required and optional environment variables."""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    initial_namespace = os.getenv("ENDOR_NAMESPACE")

    if not api_key or not api_secret or not initial_namespace:
        print("ERROR: API_KEY, API_SECRET, and ENDOR_NAMESPACE environment variables must be set.")
        print("Please set them in a .env file or directly in your environment.")
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "initial_namespace": initial_namespace,
    }


def get_token(api_key, api_secret):
    """Exchange API key/secret for a bearer token."""
    url = f"{API_URL}/auth/api-key"
    payload = {"key": api_key, "secret": api_secret}
    headers = {"Content-Type": "application/json", "Request-Timeout": "60"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json().get("token")
    except requests.exceptions.RequestException as e:
        print(f"Failed to get token: {e}")
        sys.exit(1)


def get_project_details(token, project_uuid, initial_namespace):
    """Resolve a project's name and the namespace it lives in (handles child namespaces via traverse)."""
    url = f"{API_URL}/namespaces/{initial_namespace}/projects"
    headers = {"Authorization": f"Bearer {token}", "Request-Timeout": "600"}
    params = {
        "list_parameters.filter": f"uuid=={project_uuid}",
        "list_parameters.mask": "meta.name,tenant_meta.namespace",
        "list_parameters.traverse": "true",
    }

    print(f"Fetching project details for project {project_uuid}...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        objects = response.json().get("list", {}).get("objects", [])

        if not objects:
            print(f"No project found with uuid {project_uuid} under namespace {initial_namespace}.")
            return None, None

        project_data = objects[0]
        project_name = project_data.get("meta", {}).get("name")
        namespace = project_data.get("tenant_meta", {}).get("namespace")
        print(f"Project name: {project_name}, Namespace: {namespace}")
        return project_name, namespace

    except requests.exceptions.RequestException as e:
        print(f"Failed to get project details: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return None, None


def get_default_branch(namespace, token, project_uuid):
    """Look up the project's default branch reference (e.g. refs/heads/main)."""
    url = f"{API_URL}/namespaces/{namespace}/repositories"
    headers = {"Authorization": f"Bearer {token}", "Request-Timeout": "600"}
    params = {
        "list_parameters.filter": f"meta.parent_uuid=={project_uuid}",
        "list_parameters.mask": "spec.default_branch",
        "list_parameters.traverse": "true",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        repos = response.json().get("list", {}).get("objects", [])
        if not repos:
            return None
        return repos[0].get("spec", {}).get("default_branch") or None
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to fetch default branch: {e}")
        return None


def resolve_use_main_context(branch, default_branch):
    """Use CONTEXT_TYPE_MAIN unless --branch is provided and differs from the default branch."""
    if not branch:
        return True
    if default_branch is not None:
        return branch == default_branch
    return False


def read_dependencies_file(filename):
    """Parse the dependencies input file.

    Each non-empty, non-comment line should be in ``name@version`` format. Lines
    without a version are still accepted and matched on package name only.

    Returns a list of (name, version_or_none) tuples preserving the original input.
    """
    if not os.path.exists(filename):
        print(f"ERROR: Dependencies file not found: {filename}")
        sys.exit(1)

    deps = []
    seen = set()
    with open(filename, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "@" in line:
                name, _, version = line.rpartition("@")
                name = name.strip()
                version = version.strip() or None
            else:
                name = line
                version = None

            if not name:
                continue

            key = (name.lower(), version)
            if key in seen:
                continue
            seen.add(key)
            deps.append((name, version))

    if not deps:
        print(f"ERROR: No dependencies found in {filename}.")
        sys.exit(1)

    print(f"Loaded {len(deps)} dependency entries from {filename}")
    return deps


def parse_tags(tag_args):
    """Flatten ``--tag`` arguments (which may be repeated and/or comma-separated) into a clean list."""
    tags = []
    for entry in tag_args or []:
        for piece in entry.split(","):
            piece = piece.strip()
            if piece and piece not in tags:
                tags.append(piece)
    return tags


def normalize_package_name(package_name):
    """Strip the ``<ecosystem>://`` prefix from a DependencyMetadata package name."""
    if not package_name:
        return ""
    if "://" in package_name:
        return package_name.split("://", 1)[1]
    return package_name


def fetch_project_dependencies(namespace, token, project_uuid, branch=None, default_branch=None):
    """Page through DependencyMetadata for the project in the chosen context."""
    url = f"{API_URL}/namespaces/{namespace}/dependency-metadata"
    headers = {"Authorization": f"Bearer {token}", "Request-Timeout": "600"}

    use_main_context = resolve_use_main_context(branch, default_branch)
    if use_main_context:
        context_filter = (
            f"context.type==CONTEXT_TYPE_MAIN and "
            f"spec.importer_data.project_uuid=={project_uuid}"
        )
        print("Using main context")
    else:
        context_filter = (
            f"context.id=={branch} and "
            f"spec.importer_data.project_uuid=={project_uuid}"
        )
        print(f"Using branch context: {branch}")

    params = {
        "list_parameters.filter": context_filter,
        "list_parameters.mask": "uuid,meta.name,meta.tags,spec.dependency_data.package_name,spec.dependency_data.resolved_version",
        "list_parameters.traverse": "true",
        "list_parameters.page_size": 500,
    }

    all_deps = []
    next_page_id = None
    page_num = 1

    while True:
        if next_page_id:
            params["list_parameters.page_id"] = next_page_id

        try:
            print(f"Fetching dependencies page {page_num}...")
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            data = response.json()
            objects = data.get("list", {}).get("objects", [])
            all_deps.extend(objects)

            next_page_id = data.get("list", {}).get("response", {}).get("next_page_id")
            if not next_page_id:
                break
            page_num += 1

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch dependencies: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)

    print(f"Total dependencies fetched for project: {len(all_deps)}")
    return all_deps


def find_matching_dependencies(project_dependencies, requested_deps):
    """Match each requested ``(name, version)`` against the project's DependencyMetadata records.

    Matching is case-insensitive on package name. If a version is provided in the
    input, it must match ``spec.dependency_data.resolved_version`` exactly.
    """
    requested_normalized = []
    for name, version in requested_deps:
        requested_normalized.append((name.lower(), version, name))

    matches = []
    matched_inputs = set()

    for dep in project_dependencies:
        dep_data = dep.get("spec", {}).get("dependency_data", {}) or {}
        package_name_raw = dep_data.get("package_name", "")
        resolved_version = dep_data.get("resolved_version", "") or ""
        package_name = normalize_package_name(package_name_raw)

        if not package_name:
            package_name = normalize_package_name(dep.get("meta", {}).get("name", ""))
            if "@" in package_name and not resolved_version:
                package_name, _, resolved_version = package_name.rpartition("@")

        package_name_lc = package_name.lower()

        for req_name_lc, req_version, original_name in requested_normalized:
            if package_name_lc != req_name_lc:
                continue
            if req_version and req_version != resolved_version:
                continue
            matches.append({
                "uuid": dep.get("uuid"),
                "name": package_name,
                "version": resolved_version,
                "current_tags": dep.get("meta", {}).get("tags", []) or [],
                "meta_name": dep.get("meta", {}).get("name", ""),
                "input_name": original_name,
                "input_version": req_version,
            })
            matched_inputs.add((req_name_lc, req_version))

    unmatched = [
        (original_name, version)
        for name_lc, version, original_name in requested_normalized
        if (name_lc, version) not in matched_inputs
    ]

    return matches, unmatched


def patch_dependency_tags(namespace, token, dependency_uuid, new_tags, debug=False):
    """PATCH a DependencyMetadata object's meta.tags."""
    url = f"{API_URL}/namespaces/{namespace}/dependency-metadata"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600",
    }
    payload = {
        "request": {"update_mask": "meta.tags"},
        "object": {
            "uuid": dependency_uuid,
            "meta": {"tags": new_tags},
        },
    }

    if debug:
        print(f"PATCH {url} payload={json.dumps(payload)}")

    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to update dependency {dependency_uuid}: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def merge_tags(existing_tags, new_tags, replace=False):
    """Combine existing and new tags, preserving order and avoiding duplicates."""
    if replace:
        result = []
        for tag in new_tags:
            if tag not in result:
                result.append(tag)
        return result

    result = list(existing_tags or [])
    for tag in new_tags:
        if tag not in result:
            result.append(tag)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Tag dependencies in an Endor Labs project from a text file of name@version entries."
    )
    parser.add_argument("--project_uuid", type=str, required=True, help="UUID of the project whose dependencies should be tagged.")
    parser.add_argument(
        "--dependencies-file",
        type=str,
        default="dependencies.txt",
        help="Path to the file listing dependencies to tag (default: dependencies.txt). One name@version per line.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        required=True,
        help="Tag to apply. Can be specified multiple times or as a comma-separated list (e.g. --tag risky --tag prod).",
    )
    parser.add_argument("--branch", type=str, help="Branch context to operate on (defaults to main context).")
    parser.add_argument(
        "--replace-tags",
        action="store_true",
        help="Replace existing tags instead of merging with them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without applying any updates.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable verbose request logging.")

    args = parser.parse_args()

    tags = parse_tags(args.tag)
    if not tags:
        print("ERROR: At least one non-empty tag must be provided via --tag.")
        sys.exit(1)
    print(f"Tags to apply: {tags}")

    requested_deps = read_dependencies_file(args.dependencies_file)

    env = get_env_values()
    token = get_token(env["api_key"], env["api_secret"])
    if not token:
        print("Failed to get API token.")
        sys.exit(1)

    project_name, namespace = get_project_details(token, args.project_uuid, env["initial_namespace"])
    if not namespace:
        print(f"ERROR: Could not determine namespace for project {args.project_uuid}.")
        sys.exit(1)

    default_branch = get_default_branch(namespace, token, args.project_uuid)
    if default_branch:
        print(f"Default branch for project: {default_branch}")

    project_dependencies = fetch_project_dependencies(
        namespace, token, args.project_uuid, args.branch, default_branch
    )
    if not project_dependencies:
        print(f"No dependencies found for project {args.project_uuid}.")
        sys.exit(1)

    matches, unmatched = find_matching_dependencies(project_dependencies, requested_deps)

    if unmatched:
        print(f"\nWarning: {len(unmatched)} requested dependency entries did not match any project dependency:")
        for name, version in unmatched:
            label = f"{name}@{version}" if version else name
            print(f"  - {label}")

    if not matches:
        print("\nNo matching dependencies found to tag. Exiting.")
        sys.exit(1)

    print(f"\nFound {len(matches)} dependency record(s) matching the input file.")

    updated = 0
    skipped = 0
    errors = 0

    for match in matches:
        new_tags = merge_tags(match["current_tags"], tags, replace=args.replace_tags)
        if new_tags == match["current_tags"]:
            skipped += 1
            print(
                f"  - {match['meta_name'] or match['name']}: tags already up to date "
                f"({match['current_tags']})"
            )
            continue

        action = "[DRY-RUN]" if args.dry_run else "Updating"
        print(
            f"  {action} {match['meta_name'] or match['name']} "
            f"(uuid={match['uuid']}): {match['current_tags']} -> {new_tags}"
        )

        if args.dry_run:
            continue

        success = patch_dependency_tags(namespace, token, match["uuid"], new_tags, debug=args.debug)
        if success:
            updated += 1
        else:
            errors += 1

    print("\nSummary")
    print("-------")
    print(f"  Project: {project_name} ({args.project_uuid})")
    print(f"  Namespace: {namespace}")
    print(f"  Tags applied: {tags}")
    print(f"  Matched dependencies: {len(matches)}")
    if args.dry_run:
        print(f"  Would update: {len(matches) - skipped}")
        print(f"  Already up to date: {skipped}")
    else:
        print(f"  Updated: {updated}")
        print(f"  Already up to date: {skipped}")
        print(f"  Errors: {errors}")
    if unmatched:
        print(f"  Unmatched input entries: {len(unmatched)}")

    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
