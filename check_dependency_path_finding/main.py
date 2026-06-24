"""
check_dependency_path_finding
=============================

Given a single Endor Labs finding, determine whether its DEPENDENCY PATH passes
through a specific dependency (e.g. an Atlassian package like @forge/cli), and
print the path as evidence.

Why this is needed
------------------
The full hop-by-hop dependency path is NOT a queryable field on the Finding
object:
  * Finding.spec.relationship is a *collapsed* summary (root + first direct
    dependency + vulnerable leaf). It drops intermediate hops, so it cannot tell
    you whether the path runs through a middle package such as @forge/cli.
  * DependencyMetadata only stores ONE immediate parent, not every path.

The only complete source of truth is the project's resolved dependency graph,
stored on the root PackageVersion at:
    spec.resolved_dependencies.dependency_graph   ->  { parent: [children] }

What this script does ("the magic")
-----------------------------------
1. GET the finding by uuid                -> vulnerable leaf + root PackageVersion
2. GET that PackageVersion's graph        -> the full { parent: [children] } map
3. Decide whether the finding's path goes through the requested dependency:

       a finding's path includes dependency X
           <=>  the finding's vulnerable package is a DESCENDANT of X in the graph

4. Print a concrete example path  root -> ... -> X -> ... -> leaf  as evidence.

Auth
----
Uses the ENDOR_TOKEN environment variable as a bearer token. No .env, no API key.

    export ENDOR_TOKEN=...
    python3 main.py --namespace <ns> --finding-uuid <uuid> --dependency @forge/cli

Exit codes: 0 = path passes through the dependency, 1 = it does not, 2 = error.
"""

import argparse
import os
import sys
from collections import deque

import requests

API_URL = "https://api.endorlabs.com/v1"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def pkg_name(node):
    """'npm://@forge/cli@12.13.1' -> '@forge/cli' (handles scoped npm names)."""
    s = node.split("://", 1)[-1]
    at = s.rfind("@")          # rfind so scoped names like @forge/cli survive
    return s[:at] if at > 0 else s


def pkg_name_version(node):
    """'npm://@forge/cli@12.13.1' -> '@forge/cli@12.13.1'."""
    return node.split("://", 1)[-1]


def matches_target(node, dependency, exact):
    return (pkg_name_version(node) if exact else pkg_name(node)) == dependency


def severity(level):
    """'FINDING_LEVEL_CRITICAL' -> 'CRITICAL'."""
    return (level or "").replace("FINDING_LEVEL_", "") or "UNKNOWN"


# --------------------------------------------------------------------------- #
# API calls (plain GET with an ENDOR_TOKEN bearer header)
# --------------------------------------------------------------------------- #
def get_finding(session, namespace, finding_uuid):
    url = f"{API_URL}/namespaces/{namespace}/findings/{finding_uuid}"
    params = {
        "get_parameters.mask": (
            "uuid,meta.description,meta.parent_uuid,"
            "spec.target_dependency_package_name,spec.level"
        )
    }
    resp = session.get(url, params=params, timeout=120)
    if resp.status_code != 200:
        sys.exit(f"ERROR: could not fetch finding {finding_uuid} in "
                 f"namespace {namespace}: {resp.status_code} {resp.text}")
    return resp.json()


def get_dependency_graph(session, namespace, pv_uuid):
    """Return (graph, root_node_name) for a PackageVersion."""
    url = f"{API_URL}/namespaces/{namespace}/package-versions/{pv_uuid}"
    params = {
        "get_parameters.mask": "meta.name,spec.resolved_dependencies.dependency_graph"
    }
    resp = session.get(url, params=params, timeout=120)
    if resp.status_code != 200:
        sys.exit(f"ERROR: could not fetch PackageVersion {pv_uuid}: "
                 f"{resp.status_code} {resp.text}")
    body = resp.json()
    graph = (body.get("spec", {})
                 .get("resolved_dependencies", {})
                 .get("dependency_graph"))
    root = body.get("meta", {}).get("name")
    return graph, root


# --------------------------------------------------------------------------- #
# Graph logic
# --------------------------------------------------------------------------- #
def descendants_of_target(graph, dependency, exact):
    """All package-version nodes reachable from any node matching `dependency`
    (inclusive of the matched nodes themselves)."""
    roots = [n for n in graph if matches_target(n, dependency, exact)]
    seen = set(roots)
    queue = deque(roots)
    while queue:
        for child in graph.get(queue.popleft(), []):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return roots, seen


def bfs_path(graph, start, goal):
    """Shortest node path start->goal, or None."""
    if start == goal:
        return [start]
    prev = {start: None}
    queue = deque([start])
    while queue:
        n = queue.popleft()
        for c in graph.get(n, []):
            if c not in prev:
                prev[c] = n
                if c == goal:
                    path, cur = [], c
                    while cur is not None:
                        path.append(cur)
                        cur = prev[cur]
                    return path[::-1]
                queue.append(c)
    return None


def example_path_through_target(graph, root, leaf, target_nodes):
    """One concrete path root -> ... -> <target> -> ... -> leaf (evidence)."""
    for t in target_nodes:
        head = bfs_path(graph, root, t)
        tail = bfs_path(graph, t, leaf)
        if head and tail:
            return head + tail[1:]
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description="Check whether a finding's dependency path passes through a "
                    "given dependency, and print the path.")
    ap.add_argument("--namespace", required=True,
                    help="Endor namespace the finding lives in (no traverse).")
    ap.add_argument("--finding-uuid", required=True,
                    help="UUID of the finding to inspect.")
    ap.add_argument("--dependency", required=True,
                    help="Dependency to look for in the path, e.g. '@forge/cli'. "
                         "Matched by package name unless --exact is given.")
    ap.add_argument("--exact", action="store_true",
                    help="Match name@version exactly (e.g. 'lodash@4.17.21').")
    args = ap.parse_args()

    token = os.getenv("ENDOR_TOKEN")
    if not token:
        sys.exit("ERROR: ENDOR_TOKEN environment variable is not set.\n"
                 "       export ENDOR_TOKEN=... and re-run.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}",
                            "Request-Timeout": "120"})

    # 1) Finding -> vulnerable leaf + root PackageVersion uuid
    finding = get_finding(session, args.namespace, args.finding_uuid)
    spec = finding.get("spec", {})
    meta = finding.get("meta", {})
    leaf = spec.get("target_dependency_package_name")
    pv_uuid = meta.get("parent_uuid")
    if not leaf or not pv_uuid:
        sys.exit("ERROR: this finding has no dependency target "
                 "(is it a dependency/SCA finding?). Nothing to trace.")

    # 2) Root PackageVersion -> full dependency graph
    graph, root = get_dependency_graph(session, args.namespace, pv_uuid)
    if not graph:
        sys.exit("ERROR: the project's dependency graph is not available "
                 "(spec.resolved_dependencies.dependency_graph is empty). "
                 "Has the project been scanned with dependency resolution?")

    # 3) Does the finding's path pass through the requested dependency?
    target_nodes, descendants = descendants_of_target(graph, args.dependency,
                                                       args.exact)

    print(f"Finding   : {finding.get('uuid', args.finding_uuid)}")
    print(f"            {meta.get('description', '')}")
    print(f"Severity  : {severity(spec.get('level'))}")
    print(f"Vulnerable: {pkg_name_version(leaf)}")
    print(f"Project   : {pkg_name_version(root) if root else pv_uuid}")
    print(f"Dependency: {args.dependency} ({'exact' if args.exact else 'by name'})")
    print()

    if not target_nodes:
        print(f"NOT FOUND: '{args.dependency}' does not appear anywhere in this "
              f"project's dependency graph.")
        sys.exit(1)

    if leaf not in descendants:
        print(f"NO: the finding's dependency path does NOT pass through "
              f"'{args.dependency}'.")
        print(f"    ('{args.dependency}' is in the project, but the vulnerable "
              f"package is not reached through it.)")
        sys.exit(1)

    print(f"YES: the finding's dependency path passes through '{args.dependency}'.")
    path = example_path_through_target(graph, root, leaf, target_nodes)
    if path:
        print("\nExample path:")
        for i, node in enumerate(path):
            arrow = "    " if i == 0 else " -> "
            print(f"{arrow}{pkg_name_version(node)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
