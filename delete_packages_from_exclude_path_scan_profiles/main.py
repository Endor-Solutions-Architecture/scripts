import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

APP_URL = "https://app.endorlabs.com"


load_dotenv()

ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
API_URL = "https://api.endorlabs.com/v1"

API_TOKEN = None
HEADERS = None


def get_token():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    url = f"{API_URL}/auth/api-key"
    payload = {"key": api_key, "secret": api_secret}
    headers = {"Content-Type": "application/json", "Request-Timeout": "60"}
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code == 200:
        return response.json().get("token")
    raise Exception(
        f"Failed to get token: {response.status_code}, {response.text}"
    )


def init_auth():
    global API_TOKEN, HEADERS
    API_TOKEN = get_token()
    HEADERS = {
        "User-Agent": "curl/7.68.0",
        "Accept": "*/*",
        "Authorization": f"Bearer {API_TOKEN}",
        "Request-Timeout": "600",
    }


# ---------------------------------------------------------------------------
# Generic paginated query helper against the /queries endpoint.
# ---------------------------------------------------------------------------

def run_query(namespace, kind, list_filter=None, mask=None, traverse=True):
    """Yield every object returned by a paginated `/queries` call."""
    list_parameters = {"traverse": traverse}
    if list_filter:
        list_parameters["filter"] = list_filter
    if mask:
        list_parameters["mask"] = mask

    query_data = {
        "tenant_meta": {"namespace": namespace},
        "meta": {"name": f"List {kind}"},
        "spec": {
            "query_spec": {
                "kind": kind,
                "list_parameters": list_parameters,
            }
        },
    }
    url = f"{API_URL}/namespaces/{namespace}/queries"

    next_page_token = None
    while True:
        if next_page_token:
            query_data["spec"]["query_spec"]["list_parameters"]["page_token"] = next_page_token

        response = requests.post(url, headers=HEADERS, json=query_data, timeout=600)
        if response.status_code != 200:
            print(
                f"Query for {kind} in '{namespace}' failed: "
                f"{response.status_code} {response.text}"
            )
            return

        data = response.json()
        list_block = (
            data.get("spec", {})
            .get("query_response", {})
            .get("list", {})
        )
        for obj in list_block.get("objects", []) or []:
            yield obj

        next_page_token = list_block.get("response", {}).get("next_page_token")
        if not next_page_token:
            return


# ---------------------------------------------------------------------------
# Glob -> regex conversion. Endor uses Go's RE2 for the `matches` operator.
# ---------------------------------------------------------------------------

def glob_to_regex(glob):
    """Convert a single glob pattern (gitignore-style) to an anchored regex.

    Conventions:
      `**/`  -> zero-or-more directory segments
      `/**`  -> slash followed by anything (including nothing)
      `**`   -> any characters (including `/`)
      `*`    -> any characters except `/`
      `?`    -> a single character except `/`
    """
    i, n = 0, len(glob)
    out = ["^"]
    while i < n:
        c = glob[i]
        if c == "*":
            if i + 1 < n and glob[i + 1] == "*":
                if i + 2 < n and glob[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in r".+()[]{}|^$\\":
            out.append("\\" + c)
            i += 1
        else:
            out.append(c)
            i += 1
    out.append("$")
    return "".join(out)


def globs_to_combined_regex(globs):
    """Combine multiple globs into a single case-insensitive alternation regex."""
    if not globs:
        return None
    bare_parts = [glob_to_regex(g)[1:-1] for g in globs]
    return "(?i)^(?:" + "|".join(bare_parts) + ")$"


# ---------------------------------------------------------------------------
# Endor object fetchers.
# ---------------------------------------------------------------------------

def get_scan_profiles(namespace):
    """Return summarised ScanProfile objects across the namespace tree."""
    profiles = []
    mask = (
        "uuid,meta.name,tenant_meta,"
        "spec.is_default,"
        "spec.automated_scan_parameters.excluded_paths"
    )
    for obj in run_query(
        namespace=namespace,
        kind="ScanProfile",
        mask=mask,
        traverse=True,
    ):
        spec = obj.get("spec") or {}
        params = spec.get("automated_scan_parameters") or {}
        profiles.append(
            {
                "uuid": obj.get("uuid"),
                "namespace": (obj.get("tenant_meta") or {}).get("namespace"),
                "name": (obj.get("meta") or {}).get("name"),
                "is_default": bool(spec.get("is_default")),
                "excluded_paths": list(params.get("excluded_paths") or []),
            }
        )
    return profiles


def get_projects_for_profile(profile):
    """Return [{uuid, namespace}] for every project governed by `profile`.

    For non-default profiles, projects must reference the profile by UUID.
    For default profiles, projects in the profile's namespace tree that have
    no `scan_profile_uuid` set fall back to it.
    """
    if profile["is_default"]:
        # An absent `scan_profile_uuid` field is NOT the same as `== ""`
        # in Endor's filter syntax. Cover both: missing and empty.
        list_filter = (
            'spec.scan_profile_uuid not exists '
            'or spec.scan_profile_uuid == ""'
        )
    else:
        list_filter = f'spec.scan_profile_uuid == "{profile["uuid"]}"'

    projects = []
    for obj in run_query(
        namespace=profile["namespace"],
        kind="Project",
        list_filter=list_filter,
        mask="uuid,tenant_meta,meta.name,spec.scan_profile_uuid",
        traverse=True,
    ):
        projects.append(
            {
                "uuid": obj.get("uuid"),
                "namespace": (obj.get("tenant_meta") or {}).get("namespace"),
                "name": (obj.get("meta") or {}).get("name"),
            }
        )
    return projects


def get_matching_packages(projects, regex):
    """Query PackageVersions for the given projects whose relative_path matches the regex."""
    if not projects or not regex:
        return []

    by_namespace = {}
    for p in projects:
        by_namespace.setdefault(p["namespace"], []).append(p["uuid"])

    if "'" in regex:
        print(
            "WARNING: combined regex contains a single quote, which would break "
            "the Endor filter syntax. Skipping this profile."
        )
        return []

    BATCH = 50
    found = []
    for ns, uuids in by_namespace.items():
        for i in range(0, len(uuids), BATCH):
            batch = uuids[i : i + BATCH]
            project_clause = " or ".join(f'spec.project_uuid=="{u}"' for u in batch)
            full_filter = (
                "context.type==CONTEXT_TYPE_MAIN "
                f"and ({project_clause}) "
                f"and spec.relative_path matches '{regex}'"
            )
            for obj in run_query(
                namespace=ns,
                kind="PackageVersion",
                list_filter=full_filter,
                mask="uuid,meta.name,meta.update_time,spec.project_uuid,spec.relative_path,tenant_meta",
                traverse=False,
            ):
                found.append(obj)
    return found


def write_csv(path, rows):
    fieldnames = [
        "run_namespace",
        "scan_profile_name",
        "scan_profile_uuid",
        "scan_profile_namespace",
        "scan_profile_is_default",
        "package_namespace",
        "package_uuid",
        "package_name",
        "update_time",
        "relative_path",
        "project_uuid",
        "project_name",
        "project_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"\nWrote {len(rows)} row(s) to {path}")


def delete_packages(packages):
    print(f"\nDeleting {len(packages)} package version(s)...")
    for package in packages:
        package_uuid = package.get("uuid")
        tenant_name = (package.get("tenant_meta") or {}).get("namespace")

        if not (package_uuid and tenant_name):
            print(f"  Skipping (missing uuid/namespace): {package}")
            continue

        url = f"{API_URL}/namespaces/{tenant_name}/package-versions/{package_uuid}"
        try:
            response = requests.delete(url, headers=HEADERS, timeout=60)
            if response.status_code == 200:
                print(f"  Deleted {tenant_name}/{package_uuid}")
            else:
                print(
                    f"  FAILED to delete {tenant_name}/{package_uuid}: "
                    f"{response.status_code} {response.text}"
                )
        except requests.RequestException as e:
            print(f"  Error deleting {tenant_name}/{package_uuid}: {e}")


# ---------------------------------------------------------------------------
# Entrypoint.
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find (and optionally delete) PackageVersions whose relative_path "
            "matches the excluded_paths of the scan profile that governs their "
            "project. Walks every scan profile in the namespace tree."
        )
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually delete matching package versions. Default is dry-run.",
    )
    parser.add_argument(
        "--scan-profile-uuid",
        help="Restrict processing to a single scan profile by UUID.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help=(
            "Path to write a CSV report of matched package versions. "
            "Defaults to ./excluded_packages_<namespace>_<UTC-timestamp>.csv. "
            "Pass an empty string to skip the report."
        ),
    )
    args = parser.parse_args()

    if args.csv is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_ns = re.sub(r"[^A-Za-z0-9._-]+", "_", ENDOR_NAMESPACE or "unknown")
        args.csv = f"excluded_packages_{safe_ns}_{ts}.csv"

    if not ENDOR_NAMESPACE:
        print("ENDOR_NAMESPACE env var is required.")
        sys.exit(1)

    init_auth()

    print(f"Fetching scan profiles in namespace '{ENDOR_NAMESPACE}' (traversing children)...")
    profiles = get_scan_profiles(ENDOR_NAMESPACE)
    print(f"Found {len(profiles)} scan profile(s).")

    if args.scan_profile_uuid:
        profiles = [p for p in profiles if p["uuid"] == args.scan_profile_uuid]
        if not profiles:
            print(f"No scan profile with UUID {args.scan_profile_uuid} found.")
            sys.exit(1)

    all_packages = []
    seen_uuids = set()
    rows = []  # CSV rows; one per matched package version.

    for profile in profiles:
        excluded = profile["excluded_paths"]
        kind_label = "default" if profile["is_default"] else "scoped"
        header = (
            f"\n=== Profile '{profile['name']}' ({profile['uuid']}) "
            f"[{kind_label}] in '{profile['namespace']}' ==="
        )
        print(header)

        if not excluded:
            print("  No excluded_paths configured. Skipping.")
            continue

        print(f"  excluded_paths ({len(excluded)}): {excluded}")

        regex = globs_to_combined_regex(excluded)
        print(f"  Combined regex: {regex}")

        projects = get_projects_for_profile(profile)
        print(f"  Governs {len(projects)} project(s).")
        if not projects:
            continue

        project_lookup = {p["uuid"]: p for p in projects}

        packages = get_matching_packages(projects, regex)
        print(f"  Matched {len(packages)} package version(s).")

        for pkg in packages:
            uuid = pkg.get("uuid")
            if not uuid or uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)
            all_packages.append(pkg)
            spec = pkg.get("spec") or {}
            tn = (pkg.get("tenant_meta") or {}).get("namespace")
            meta = pkg.get("meta") or {}
            package_name = meta.get("name", "")
            update_time = meta.get("update_time", "")
            project_uuid = spec.get("project_uuid")
            project = project_lookup.get(project_uuid, {})
            project_name = project.get("name", "")
            project_namespace = project.get("namespace") or tn
            project_url = (
                f"{APP_URL}/t/{project_namespace}/projects/{project_uuid}"
                "/versions/default/inventory/packages"
                if project_namespace and project_uuid
                else ""
            )
            print(
                f"    - {tn}/{uuid}  project={project_uuid}  "
                f"path={spec.get('relative_path')}"
            )
            rows.append(
                {
                    "run_namespace": ENDOR_NAMESPACE,
                    "scan_profile_name": profile["name"],
                    "scan_profile_uuid": profile["uuid"],
                    "scan_profile_namespace": profile["namespace"],
                    "scan_profile_is_default": profile["is_default"],
                    "package_namespace": tn,
                    "package_uuid": uuid,
                    "package_name": package_name,
                    "update_time": update_time,
                    "relative_path": spec.get("relative_path", ""),
                    "project_uuid": project_uuid or "",
                    "project_name": project_name,
                    "project_url": project_url,
                }
            )

    print(
        f"\n========== TOTAL: {len(all_packages)} unique PackageVersion(s) "
        f"would be deleted =========="
    )

    if args.csv:
        write_csv(args.csv, rows)

    if args.no_dry_run:
        delete_packages(all_packages)
    else:
        print(
            "Dry-run mode: no deletions performed. "
            "Re-run with --no-dry-run to delete."
        )


if __name__ == "__main__":
    main()
