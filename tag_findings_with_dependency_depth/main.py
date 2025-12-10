#!/usr/bin/env python3
"""
Tag Findings with Dependency Depth

This script tags vulnerability findings in Endor Labs with their dependency depth.
Direct dependencies are tagged with `dependency-depth:0`, first degree transitive
dependencies with `dependency-depth:1`, and so on.

Usage:
    # Tag findings for a specific project (test mode)
    python main.py --namespace my-namespace --project-uuid <uuid> --test

    # Tag findings for a specific project (apply changes)
    python main.py --namespace my-namespace --project-uuid <uuid>

    # Tag findings for all projects in namespace
    python main.py --namespace my-namespace --all-projects
"""

import os
import sys
import re
import csv
import json
import argparse
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from dotenv import load_dotenv
import requests


# Configure logging
logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)4s - %(funcName)20s()] %(message)s"
logging.basicConfig(format=FORMAT)

DEPTH_TAG_PREFIX = "dependency-depth:"
DEPTH_TAG_PATTERN = re.compile(rf"^{re.escape(DEPTH_TAG_PREFIX)}\d+$")


def get_endor_token() -> str:
    """Get Endor token either directly or by authenticating with API credentials."""
    token = os.getenv('ENDOR_TOKEN')
    if token:
        return token

    key = os.getenv('ENDOR_API_CREDENTIALS_KEY')
    secret = os.getenv('ENDOR_API_CREDENTIALS_SECRET')

    if not key or not secret:
        print("Error: Either ENDOR_TOKEN or both ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET must be set")
        sys.exit(1)

    try:
        response = requests.post(
            "https://api.endorlabs.com/v1/auth/api-key",
            json={"key": key, "secret": secret},
            timeout=60
        )
        if response.status_code != 200:
            print(f"Error: Failed to get token from API. Status code: {response.status_code}")
            sys.exit(1)

        token = response.json().get('token')
        if not token:
            print("Error: No token in API response")
            sys.exit(1)

        return token
    except Exception as e:
        print(f"Error getting token from API: {e}")
        sys.exit(1)


class EndorAPIClient:
    """Simple client for Endor Labs API operations."""

    def __init__(self, namespace: str, token: str, debug: bool = False, timeout: int = 60):
        self.namespace = namespace
        self.token = token
        self.debug = debug
        self.timeout = timeout
        self.base_url = "https://api.endorlabs.com/v1"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/jsoncompact",
            "Request-Timeout": str(self.timeout)
        }

    def _get_paginated(
        self,
        endpoint: str,
        params: Dict[str, str],
        mask: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all results from a paginated endpoint.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            mask: Optional field mask to limit returned fields (comma-separated paths)
        """
        url = f"{self.base_url}/namespaces/{self.namespace}/{endpoint}"
        all_results = []
        page_id = None

        while True:
            request_params = {**params, "list_parameters.page_size": "500"}
            if page_id:
                request_params["list_parameters.page_id"] = page_id
            if mask:
                request_params["list_parameters.mask"] = mask

            if self.debug:
                logger.debug(f"GET {url} params={request_params}")

            response = requests.get(url, headers=self._headers(), params=request_params, timeout=self.timeout)

            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                raise Exception(f"API error: {response.status_code}")

            data = response.json()
            objects = data.get('list', {}).get('objects', [])
            all_results.extend(objects)

            page_id = data.get('list', {}).get('response', {}).get('next_page_id')
            if not page_id:
                break

        return all_results

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects in the namespace."""

        mask = "uuid,meta.name"
        return self._get_paginated("projects", {}, mask=mask)

    def get_project(self, project_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a specific project by UUID."""
        url = f"{self.base_url}/namespaces/{self.namespace}/projects/{project_uuid}"

        params = {"get_parameters.mask": "uuid,meta.name"}
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")

    def list_package_versions_for_project(self, project_uuid: str) -> List[Dict[str, Any]]:
        """List PackageVersions for a project with CONTEXT_TYPE_MAIN."""
        params = {
            "list_parameters.filter": f"spec.project_uuid=={project_uuid} and context.type==CONTEXT_TYPE_MAIN"
        }

        mask = "uuid,meta.name,spec.resolved_dependencies.dependency_graph"
        return self._get_paginated("package-versions", params, mask=mask)

    def get_package_version(self, package_version_uuid: str) -> Optional[Dict[str, Any]]:
        """Get a specific PackageVersion by UUID."""
        url = f"{self.base_url}/namespaces/{self.namespace}/package-versions/{package_version_uuid}"
        
        params = {"get_parameters.mask": "uuid,meta.name,spec.resolved_dependencies.dependency_graph"}
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")

    def list_vulnerability_findings_for_project(self, project_uuid: str) -> List[Dict[str, Any]]:
        """
        List all vulnerability findings for a project with CONTEXT_TYPE_MAIN.

        Fetches all findings at once to avoid per-PackageVersion API calls.
        Results can be grouped by meta.parent_uuid to associate with PackageVersions.
        """
        params = {
            "list_parameters.filter": (
                f"spec.project_uuid=={project_uuid} and "
                "context.type==CONTEXT_TYPE_MAIN and "
                "spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]"
            )
        }
        # Include meta.parent_uuid so we can group by PackageVersion
        mask = "uuid,meta.description,meta.tags,meta.parent_uuid,spec.target_dependency_package_name"
        return self._get_paginated("findings", params, mask=mask)

    def update_finding_tags(self, finding_uuid: str, tags: List[str]) -> bool:
        """Update the tags on a finding using update_mask."""
        url = f"{self.base_url}/namespaces/{self.namespace}/findings"
        payload = {
            "request": {
                "update_mask": "meta.tags"
            },
            "object": {
                "uuid": finding_uuid,
                "meta": {
                    "tags": tags
                }
            }
        }

        if self.debug:
            logger.debug(f"PATCH {url} payload={json.dumps(payload, indent=2)}")

        response = requests.patch(url, headers=self._headers(), json=payload, timeout=self.timeout)

        if response.status_code == 200:
            return True
        else:
            logger.error(f"Failed to update finding {finding_uuid}: {response.status_code} - {response.text}")
            return False


def compute_dependency_depths(dependency_graph: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Compute the minimum depth for each dependency in the graph.

    The dependency_graph maps each dependency to its direct children.
    Root dependencies (those not appearing as children of any other) are depth 0.

    Uses BFS to find minimum depth from any root to each dependency.

    Args:
        dependency_graph: Dict mapping purl -> list of child purls

    Returns:
        Dict mapping purl -> minimum depth (0 for direct, 1+ for transitive)
    """
    if not dependency_graph:
        return {}

    # Find all dependencies that appear as children
    all_children: Set[str] = set()
    for children in dependency_graph.values():
        all_children.update(children)

    # Root dependencies are those in the graph keys but not as children of anything
    # These are the direct dependencies (depth 0)
    roots = set(dependency_graph.keys()) - all_children

    if not roots:
        # Edge case: circular dependencies only, no clear roots
        # Treat all as depth 0
        logger.warning("No root dependencies found (possible circular dependency graph)")
        return {dep: 0 for dep in dependency_graph.keys()}

    # BFS from all roots simultaneously to find minimum depth
    depths: Dict[str, int] = {}
    queue: deque = deque()

    # Initialize: all roots are at depth 0
    for root in roots:
        depths[root] = 0
        queue.append(root)

    # BFS traversal
    while queue:
        current = queue.popleft()
        current_depth = depths[current]

        # Get children of current dependency
        children = dependency_graph.get(current, [])
        for child in children:
            # Only process if we haven't seen this child, or found a shorter path
            if child not in depths or depths[child] > current_depth + 1:
                depths[child] = current_depth + 1
                queue.append(child)

    return depths


def get_depth_tag(depth: int) -> str:
    """Generate the tag string for a given depth."""
    return f"{DEPTH_TAG_PREFIX}{depth}"


def is_depth_tag(tag: str) -> bool:
    """Check if a tag is a dependency-depth tag."""
    return bool(DEPTH_TAG_PATTERN.match(tag))


def compute_tag_changes(
    current_tags: List[str],
    target_depth: Optional[int]
) -> Tuple[List[str], bool, str]:
    """
    Compute what the new tags should be for a finding.

    Args:
        current_tags: Current tags on the finding
        target_depth: The correct depth, or None if depth couldn't be determined

    Returns:
        Tuple of (new_tags, needs_update, change_description)
    """
    # Separate depth tags from other tags
    other_tags = [t for t in current_tags if not is_depth_tag(t)]
    current_depth_tags = [t for t in current_tags if is_depth_tag(t)]

    if target_depth is None:
        # Can't determine depth - remove any existing depth tags
        if current_depth_tags:
            return other_tags, True, f"remove {current_depth_tags} (depth unknown)"
        return current_tags, False, "no change (depth unknown)"

    target_tag = get_depth_tag(target_depth)

    # Check if correct tag already present
    if target_tag in current_depth_tags and len(current_depth_tags) == 1:
        return current_tags, False, "no change (already correct)"

    # Build new tag list with the correct depth tag
    new_tags = other_tags + [target_tag]

    # Describe the change
    if current_depth_tags:
        change_desc = f"replace {current_depth_tags} with [{target_tag}]"
    else:
        change_desc = f"add [{target_tag}]"

    return new_tags, True, change_desc


class FindingTagger:
    """Handles tagging findings with dependency depth."""

    # CSV column headers
    CSV_HEADERS = [
        "finding_uuid",
        "project_uuid",
        "project_name",
        "package_version_uuid",
        "package_version_name",
        "target_dependency",
        "depth",
        "status",
        "change",
        "current_tags",
        "new_tags",
        "finding_description"
    ]

    def __init__(
        self,
        namespace: str,
        debug: bool = False,
        test_mode: bool = True,
        timeout: int = 60
    ):
        self.namespace = namespace
        self.debug = debug
        self.test_mode = test_mode
        self.token = get_endor_token()
        self.client = EndorAPIClient(namespace, self.token, debug, timeout)

        if debug:
            logger.setLevel(logging.DEBUG)

        # Create timestamped output files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = "test" if test_mode else "applied"
        self.output_file = f"dependency_depth_tags_{timestamp}_{mode_suffix}.csv"

        # Initialize CSV file with headers
        with open(self.output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
            writer.writeheader()

        print(f"Output will be written to: {self.output_file}")

    def _write_csv_row(self, log_entry: Dict[str, Any]) -> None:
        """Write a single log entry to the CSV file."""
        row = {
            "finding_uuid": log_entry['finding_uuid'],
            "project_uuid": log_entry['project_uuid'],
            "project_name": log_entry['project_name'],
            "package_version_uuid": log_entry['package_version_uuid'],
            "package_version_name": log_entry['package_version_name'],
            "target_dependency": log_entry['target_dependency'],
            "depth": log_entry['depth'] if log_entry['depth'] is not None else "unknown",
            "status": log_entry['status'],
            "change": log_entry['change'],
            "current_tags": ";".join(log_entry['current_tags']) if log_entry['current_tags'] else "",
            "new_tags": ";".join(log_entry['new_tags']) if log_entry['new_tags'] else "",
            "finding_description": log_entry['finding_description']
        }
        with open(self.output_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
            writer.writerow(row)

    def process_package_version(
        self,
        package_version: Dict[str, Any],
        project_uuid: str,
        project_name: str,
        findings: List[Dict[str, Any]]
    ) -> Tuple[int, int, int, List[Dict[str, Any]], bool]:
        """
        Process vulnerability findings for a PackageVersion.

        Args:
            package_version: The PackageVersion object
            project_uuid: UUID of the parent project
            project_name: Name of the parent project (for logging)
            findings: Pre-fetched findings for this PackageVersion

        Returns:
            Tuple of (processed_count, updated_count, error_count, change_log, skipped_pv)
            skipped_pv is True if the PackageVersion was skipped due to missing dependency graph
        """
        pv_uuid = package_version['uuid']
        pv_name = package_version.get('meta', {}).get('name', pv_uuid)

        if self.debug:
            logger.debug(f"Processing PackageVersion: {pv_name}")

        # Get dependency graph - handle missing/null resolved_dependencies
        resolved_deps = package_version.get('spec', {}).get('resolved_dependencies')
        if resolved_deps is None:
            if self.debug:
                logger.debug(f"PackageVersion {pv_name} has no resolved_dependencies, skipping")
            return 0, 0, 0, [], True

        dep_graph = resolved_deps.get('dependency_graph', {})
        if not dep_graph:
            if self.debug:
                logger.debug(f"PackageVersion {pv_name} has empty dependency_graph, skipping")
            return 0, 0, 0, [], True

        # Compute depths for all dependencies
        depth_map = compute_dependency_depths(dep_graph)

        if self.debug:
            logger.debug(f"Computed depths for {len(depth_map)} dependencies")
            logger.debug(f"Processing {len(findings)} vulnerability findings")

        processed = 0
        updated = 0
        errors = 0
        change_log: List[Dict[str, Any]] = []

        for finding in findings:
            finding_uuid = finding['uuid']
            finding_desc = finding.get('meta', {}).get('description', 'No description')[:60]
            target_dep = finding.get('spec', {}).get('target_dependency_package_name', '')
            current_tags = finding.get('meta', {}).get('tags', [])

            # Look up depth for this dependency
            depth = depth_map.get(target_dep)

            # Compute what changes are needed
            new_tags, needs_update, change_desc = compute_tag_changes(current_tags, depth)

            log_entry = {
                'finding_uuid': finding_uuid,
                'project_uuid': project_uuid,
                'project_name': project_name,
                'package_version_uuid': pv_uuid,
                'package_version_name': pv_name,
                'finding_description': finding_desc,
                'target_dependency': target_dep,
                'depth': depth,
                'current_tags': current_tags,
                'new_tags': new_tags,
                'change': change_desc,
                'needs_update': needs_update,
            }

            if needs_update:
                if self.test_mode:
                    log_entry['status'] = 'would_update'
                else:
                    success = self.client.update_finding_tags(finding_uuid, new_tags)
                    if success:
                        log_entry['status'] = 'updated'
                        updated += 1
                    else:
                        log_entry['status'] = 'error'
                        errors += 1
            else:
                log_entry['status'] = 'skipped'

            # Write to CSV
            self._write_csv_row(log_entry)

            change_log.append(log_entry)
            processed += 1

        return processed, updated, errors, change_log, False

    def process_project(self, project_uuid: str) -> Tuple[int, int, int, List[Dict[str, Any]], List[str]]:
        """
        Process all PackageVersions in a project.

        Returns:
            Tuple of (processed_count, updated_count, error_count, change_log, skipped_package_versions)
        """
        # Get project info
        project = self.client.get_project(project_uuid)
        if not project:
            print(f"Error: Project {project_uuid} not found")
            return 0, 0, 1, [], []

        project_name = project.get('meta', {}).get('name', project_uuid)
        print(f"\nProcessing project: {project_name}")

        # Get all PackageVersions for this project
        package_versions = self.client.list_package_versions_for_project(project_uuid)
        print(f"  Found {len(package_versions)} PackageVersion(s) with CONTEXT_TYPE_MAIN")

        # Pre-fetch all vulnerability findings for the project in one set of API calls
        # This is much more efficient than fetching per-PackageVersion, and has better indexes.
        all_findings = self.client.list_vulnerability_findings_for_project(project_uuid)
        print(f"  Found {len(all_findings)} vulnerability finding(s)")

        # Group findings by their parent PackageVersion UUID
        findings_by_pv: Dict[str, List[Dict[str, Any]]] = {}
        for finding in all_findings:
            parent_uuid = finding.get('meta', {}).get('parent_uuid', '')
            if parent_uuid:
                if parent_uuid not in findings_by_pv:
                    findings_by_pv[parent_uuid] = []
                findings_by_pv[parent_uuid].append(finding)

        total_processed = 0
        total_updated = 0
        total_errors = 0
        all_changes: List[Dict[str, Any]] = []
        skipped_pvs: List[str] = []

        for pv in package_versions:
            pv_uuid = pv['uuid']
            pv_name = pv.get('meta', {}).get('name', pv_uuid)
            # Get pre-fetched findings for this PackageVersion
            pv_findings = findings_by_pv.get(pv_uuid, [])
            processed, updated, errors, changes, skipped = self.process_package_version(
                pv, project_uuid, project_name, pv_findings
            )
            if skipped:
                skipped_pvs.append(pv_name)
                print(f"    Skipped PackageVersion (no dependency graph): {pv_name}")
            total_processed += processed
            total_updated += updated
            total_errors += errors
            all_changes.extend(changes)

        return total_processed, total_updated, total_errors, all_changes, skipped_pvs

    def process_all_projects(self) -> Tuple[int, int, int, List[Dict[str, Any]], List[str]]:
        """
        Process all projects in the namespace.

        Returns:
            Tuple of (processed_count, updated_count, error_count, change_log, skipped_package_versions)
        """
        print(f"Fetching all projects in namespace: {self.namespace}")
        projects = self.client.list_projects()
        print(f"Found {len(projects)} project(s)")

        total_processed = 0
        total_updated = 0
        total_errors = 0
        all_changes: List[Dict[str, Any]] = []
        all_skipped_pvs: List[str] = []

        for project in projects:
            project_uuid = project['uuid']
            processed, updated, errors, changes, skipped_pvs = self.process_project(project_uuid)
            total_processed += processed
            total_updated += updated
            total_errors += errors
            all_changes.extend(changes)
            all_skipped_pvs.extend(skipped_pvs)

        return total_processed, total_updated, total_errors, all_changes, all_skipped_pvs

    def print_summary(
        self,
        processed: int,
        updated: int,
        errors: int,
        change_log: List[Dict[str, Any]],
        skipped_pvs: List[str]
    ) -> None:
        """Print a summary of the changes."""
        print("\n" + "=" * 80)

        if self.test_mode:
            print("TEST MODE - No changes were made")
            print("=" * 80)

        # Group changes by status
        would_update = [c for c in change_log if c['status'] == 'would_update']
        actually_updated = [c for c in change_log if c['status'] == 'updated']
        errored = [c for c in change_log if c['status'] == 'error']
        already_correct = [c for c in change_log if c['status'] == 'skipped' and c['depth'] is not None]
        depth_unknown = [c for c in change_log if c['depth'] is None]

        print(f"\nSummary:")
        print(f"  Total findings processed: {processed}")

        if self.test_mode:
            print(f"  Would update: {len(would_update)}")
        else:
            print(f"  Updated: {len(actually_updated)}")

        print(f"  Already correct (skipped): {len(already_correct)}")
        print(f"  Errors: {len(errored)}")
        print(f"  Depth unknown (dependency not in graph): {len(depth_unknown)}")

        if skipped_pvs:
            print(f"  PackageVersions skipped (no dependency graph): {len(skipped_pvs)}")

        # Print details of changes
        changes_to_show = would_update if self.test_mode else actually_updated
        if changes_to_show:
            print(f"\n{'Planned' if self.test_mode else 'Applied'} changes:")
            print("-" * 80)
            for entry in changes_to_show[:50]:  # Limit output
                print(f"  Finding: {entry['finding_uuid']}")
                print(f"    Project: {entry['project_name']}")
                print(f"    Dependency: {entry['target_dependency']}")
                print(f"    Depth: {entry['depth']}")
                print(f"    Change: {entry['change']}")
                print()

            if len(changes_to_show) > 50:
                print(f"  ... and {len(changes_to_show) - 50} more")

        # Show findings where depth couldn't be determined
        if depth_unknown:
            print(f"\nFindings with unknown depth (dependency not found in graph):")
            print("-" * 80)
            for entry in depth_unknown[:20]:
                print(f"  Finding: {entry['finding_uuid']}")
                print(f"    Dependency: {entry['target_dependency']}")
                print(f"    Description: {entry['finding_description']}")
                print()

            if len(depth_unknown) > 20:
                print(f"  ... and {len(depth_unknown) - 20} more")

        if errored:
            print(f"\nErrors:")
            print("-" * 80)
            for entry in errored:
                print(f"  Finding: {entry['finding_uuid']} - {entry['change']}")

        if skipped_pvs:
            print(f"\nPackageVersions skipped (no dependency graph):")
            print("-" * 80)
            for pv_name in skipped_pvs[:20]:
                print(f"  {pv_name}")
            if len(skipped_pvs) > 20:
                print(f"  ... and {len(skipped_pvs) - 20} more")

        # Remind user about CSV output
        print(f"\nComplete results written to: {self.output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Tag vulnerability findings with their dependency depth',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test mode for a specific project
  python main.py --namespace my-ns --project-uuid abc123 --test

  # Apply changes for a specific project
  python main.py --namespace my-ns --project-uuid abc123

  # Process all projects in namespace (test mode)
  python main.py --namespace my-ns --all-projects --test

  # Process all projects (apply changes)
  python main.py --namespace my-ns --all-projects
"""
    )

    parser.add_argument(
        '--namespace',
        required=True,
        help='Endor Labs namespace'
    )

    # Project selection (mutually exclusive)
    project_group = parser.add_mutually_exclusive_group(required=True)
    project_group.add_argument(
        '--project-uuid',
        help='UUID of a specific project to process'
    )
    project_group.add_argument(
        '--all-projects',
        action='store_true',
        help='Process all projects in the namespace'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: show what changes would be made without applying them'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=60,
        help='API request timeout in seconds (default: 60)'
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Default to test mode if --test flag is provided, otherwise apply changes
    test_mode = args.test

    if not test_mode:
        print("\n*** LIVE MODE - Changes will be applied ***")
        print("Use --test flag to preview changes without applying them\n")
    else:
        print("\n*** TEST MODE - No changes will be made ***\n")

    # Create tagger
    tagger = FindingTagger(
        namespace=args.namespace,
        debug=args.debug,
        test_mode=test_mode,
        timeout=args.timeout
    )

    # Process projects
    if args.project_uuid:
        processed, updated, errors, changes, skipped_pvs = tagger.process_project(args.project_uuid)
    else:
        processed, updated, errors, changes, skipped_pvs = tagger.process_all_projects()

    # Print summary
    tagger.print_summary(processed, updated, errors, changes, skipped_pvs)

    # Exit with error code if there were errors
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()

