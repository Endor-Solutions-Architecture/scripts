#!/usr/bin/env python3
"""
Script to search for dependencies and find which projects use them.
"""

import argparse
import json
import os
import stat
import sys
import csv
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = 'https://api.endorlabs.com/v1'

def get_env_values():
    """Get necessary values from environment variables."""
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
        "initial_namespace": initial_namespace
    }

TOKEN_REFRESH_MARGIN_SECONDS = 60


class TokenManager:
    """Handles API token lifecycle: fetch, cache, and auto-refresh before expiry."""

    def __init__(self, api_key, api_secret):
        self._api_key = api_key
        self._api_secret = api_secret
        self._token = None
        self._expires_at = 0

    def _fetch_token(self):
        url = f"{API_URL}/auth/api-key"
        payload = {"key": self._api_key, "secret": self._api_secret}
        headers = {"Content-Type": "application/json", "Request-Timeout": "60"}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=600)
            response.raise_for_status()
            data = response.json()
            self._token = data.get("token")
            expiry = data.get("expiration_time")
            if expiry:
                import time as _time
                try:
                    self._expires_at = int(
                        datetime.fromisoformat(
                            expiry.replace("Z", "+00:00")
                        ).timestamp()
                    )
                except (ValueError, TypeError):
                    self._expires_at = int(_time.time()) + 3600
            else:
                import time as _time
                self._expires_at = int(_time.time()) + 3600
            if not self._token:
                print("ERROR: API returned empty token.")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Failed to get token: {type(e).__name__}")
            sys.exit(1)

    @property
    def token(self):
        import time as _time
        if (
            self._token is None
            or _time.time() >= self._expires_at - TOKEN_REFRESH_MARGIN_SECONDS
        ):
            self._fetch_token()
        return self._token


def parse_dependency(dependency_str):
    """Parse dependency string in format ecosystem://dependency@version."""
    try:
        if '://' not in dependency_str:
            raise ValueError("Invalid format: missing '://'")
        
        ecosystem, rest = dependency_str.split('://', 1)
        
        if '@' not in rest:
            raise ValueError("Invalid format: missing '@' for version")
        
        dependency, version = rest.rsplit('@', 1)
        
        return {
            'ecosystem': ecosystem,
            'dependency': dependency,
            'version': version,
            'full_name': f"{ecosystem}://{dependency}"
        }
    except Exception as e:
        print(f"Error parsing dependency '{dependency_str}': {e}")
        print("Expected format: ecosystem://dependency@version")
        return None


def _namespace_in_subtree(fqn, root_namespace):
    return fqn == root_namespace or fqn.startswith(root_namespace + ".")


def _parse_list_response_body(data):
    lst = data.get("list")
    if lst is None and isinstance(data.get("spec"), dict):
        lst = data["spec"].get("list")
    return lst or {}


def _namespace_fqn_from_list_object(obj, root_namespace):
    """
    Extract FQDN from a Namespace list object. spec.full_name is the object's own
    FQDN; tenant_meta.namespace is its parent. Check full_name first so we discover
    child namespaces instead of re-adding the parent.
    """
    spec = obj.get("spec") or {}
    tm = obj.get("tenant_meta") or {}
    meta = obj.get("meta") or {}
    for candidate in (spec.get("full_name"), tm.get("namespace"), meta.get("name")):
        if not candidate:
            continue
        if candidate == root_namespace or candidate.startswith(root_namespace + "."):
            return candidate
    return None


def collect_namespace_fqdns(token_mgr, root_namespace):
    """
    List fully qualified namespace names under root_namespace (ListNamespaces API,
    subtree traverse). Shown for reference before the dependency query.
    """
    encoded = urllib.parse.quote(root_namespace, safe="")
    url = f"{API_URL}/namespaces/{encoded}/namespaces"
    discovered = {root_namespace}
    next_page_token = None
    while True:
        params = {
            "list_parameters.traverse": "true",
            "list_parameters.page_size": "500",
        }
        if next_page_token is not None:
            params["list_parameters.page_token"] = str(next_page_token)
        try:
            headers = {
                "Authorization": f"Bearer {token_mgr.token}",
                "Request-Timeout": "600",
            }
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            data = response.json()
            lst = _parse_list_response_body(data)
            for obj in lst.get("objects") or []:
                fqn = _namespace_fqn_from_list_object(obj, root_namespace)
                if fqn:
                    discovered.add(fqn)
            next_page_token = (lst.get("response") or {}).get("next_page_token")
            if not next_page_token:
                break
        except requests.exceptions.RequestException as e:
            print(f"Failed to list namespaces under {root_namespace!r}: {type(e).__name__}: {e.response.status_code if hasattr(e, 'response') and e.response is not None else str(e)}")
            break

    rest = sorted(ns for ns in discovered if ns != root_namespace)
    ordered = [root_namespace] + rest
    print(
        f"\nResolved {len(ordered)} namespace FQDN(s) under {root_namespace!r} "
        f"(ListNamespaces subtree):"
    )
    for fqn in ordered:
        print(f"  - {fqn}")
    return ordered


def _query_dependency_in_namespace(token_mgr, namespace_fqdn, dependency_info):
    """
    POST .../namespaces/{namespace_fqdn}/queries for DependencyMetadata (no traverse).
    Project join also without traverse — scoped to the same namespace.
    """
    encoded = urllib.parse.quote(namespace_fqdn, safe="")
    url = f"{API_URL}/namespaces/{encoded}/queries"

    query_payload = {
        "meta": {
            "name": f"Dependencies with Project Info: {dependency_info['full_name']}"
        },
        "spec": {
            "query_spec": {
                "kind": "DependencyMetadata",
                "list_parameters": {
                    "filter": (
                        f"context.type==CONTEXT_TYPE_MAIN and "
                        f"spec.dependency_data.package_name=={dependency_info['full_name']} and "
                        f"spec.dependency_data.resolved_version=={dependency_info['version']}"
                    ),
                    "mask": "meta.name,spec.dependency_data,spec.importer_data",
                },
                "references": [
                    {
                        "connect_from": "spec.importer_data.project_uuid",
                        "connect_to": "uuid",
                        "query_spec": {
                            "kind": "Project",
                            "list_parameters": {
                                "mask": "uuid,meta.name",
                            },
                        },
                    }
                ],
            }
        },
    }

    results = []
    next_page_token = None
    page_num = 1

    while True:
        if next_page_token:
            query_payload["spec"]["query_spec"]["list_parameters"][
                "page_token"
            ] = next_page_token

        try:
            print(f"  Page {page_num}...")
            headers = {
                "Authorization": f"Bearer {token_mgr.token}",
                "Content-Type": "application/json",
                "Request-Timeout": "600",
            }
            response = requests.post(url, headers=headers, json=query_payload, timeout=600)
            response.raise_for_status()

            data = response.json()
            query_response = data.get("spec", {}).get("query_response", {})
            objects = query_response.get("list", {}).get("objects", [])
            print(f"  Received {len(objects)} row(s) on page {page_num}")

            for obj in objects:
                dep_data = obj.get("spec", {}).get("dependency_data", {})
                importer_data = obj.get("spec", {}).get("importer_data", {})

                project_name = ""
                meta_refs = obj.get("meta", {}).get("references", {})
                if "Project" in meta_refs:
                    project_objects = (
                        meta_refs["Project"].get("list", {}).get("objects", [])
                    )
                    if project_objects:
                        project_name = (
                            project_objects[0].get("meta", {}).get("name", "")
                        )

                result = {
                    "namespace_fqdn": namespace_fqdn,
                    "namespace": namespace_fqdn,
                    "project_uuid": importer_data.get("project_uuid", ""),
                    "project_name": project_name,
                    "dependency_name": dep_data.get("package_name", ""),
                    "dependency_version": dep_data.get("resolved_version", ""),
                    "dependency_scope": dep_data.get("scope", ""),
                    "parent_package_version_name": importer_data.get(
                        "package_version_name", ""
                    ),
                }
                results.append(result)
                print(
                    f"    Found {result['dependency_name']}@{result['dependency_version']} "
                    f"in {result['project_name']} ({result['project_uuid']}) "
                    f"[namespace={namespace_fqdn}]"
                )
                if result["parent_package_version_name"]:
                    print(
                        f"      └── Parent package version: "
                        f"{result['parent_package_version_name']}"
                    )

            query_response = data.get("spec", {}).get("query_response", {})
            next_page_token = query_response.get("list", {}).get("response", {}).get(
                "next_page_token"
            )
            if not next_page_token:
                break

            page_num += 1

        except requests.exceptions.RequestException as e:
            print(f"  Failed querying {namespace_fqdn!r}: {type(e).__name__}: {e.response.status_code if hasattr(e, 'response') and e.response is not None else str(e)}")
            break

    return results


def search_dependency_usage(token_mgr, root_namespace, dependency_info):
    """
    1. ListNamespaces (subtree traverse) to discover all FQDNs.
    2. For each FQDN, POST DependencyMetadata query with no traverse, using the
       namespace FQDN in the URL path. Each row is tagged with that FQDN.
    """
    print(
        f"\nSearching {dependency_info['full_name']}@{dependency_info['version']} "
        f"across all namespaces under {root_namespace!r}..."
    )
    ordered_fqdns = collect_namespace_fqdns(token_mgr, root_namespace)

    combined = []
    for fqn in ordered_fqdns:
        print(
            f"\nQuerying DependencyMetadata in {fqn!r} — "
            f"{dependency_info['full_name']}@{dependency_info['version']}"
        )
        combined.extend(
            _query_dependency_in_namespace(token_mgr, fqn, dependency_info)
        )
    return combined


def _write_file_restricted(filename, write_fn):
    """Write a file and set permissions to owner-only (0600)."""
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        with os.fdopen(fd, "w") as f:
            write_fn(f)
    except Exception:
        os.close(fd)
        raise


def save_results_json(results, filename):
    """Save results to JSON file (owner-only permissions)."""
    try:
        _write_file_restricted(filename, lambda f: json.dump(results, f, indent=2))
        print(f"Results saved to JSON: {filename}")
    except Exception as e:
        print(f"Error saving JSON file: {e}")

def save_results_csv(results, filename):
    """Save results to CSV file (owner-only permissions)."""
    if not results:
        print("No results to save to CSV")
        return
    
    try:
        preferred = [
            "namespace_fqdn",
            "namespace",
            "searched_dependency",
            "project_name",
            "project_uuid",
            "dependency_name",
            "dependency_version",
            "dependency_scope",
            "parent_package_version_name",
        ]
        extras = set()
        for result in results:
            extras.update(result.keys())
        fieldnames = [c for c in preferred if c in extras]
        fieldnames.extend(sorted(c for c in extras if c not in fieldnames))

        def write_csv(f):
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result)

        _write_file_restricted(filename, write_csv)
        print(f"Results saved to CSV: {filename}")
    except Exception as e:
        print(f"Error saving CSV file: {e}")

def display_results(results, dependency_info, root_namespace=None):
    """Display results on terminal."""
    print(f"\n{'='*60}")
    print(f"SEARCH RESULTS for {dependency_info['full_name']}@{dependency_info['version']}")
    print(f"{'='*60}")
    
    if not results:
        print("No projects found using this dependency.")
        return
    
    print(f"Found {len(results)} usage(s) across {len(set(r['namespace'] for r in results))} namespace(s)")
    print()
    
    # Group by namespace and project
    grouped = {}
    for result in results:
        namespace = result.get("namespace") or result.get("namespace_fqdn") or ""
        project_name = result['project_name'] or 'Unknown Project'
        project_key = f"{project_name} ({result['project_uuid']})"
        
        if namespace not in grouped:
            grouped[namespace] = {}
        if project_key not in grouped[namespace]:
            grouped[namespace][project_key] = []
        
        grouped[namespace][project_key].append(result)
    
    keys = list(grouped.keys())
    if root_namespace and root_namespace in keys:
        namespace_order = [root_namespace] + sorted(k for k in keys if k != root_namespace)
    else:
        namespace_order = sorted(keys)

    for namespace in namespace_order:
        projects = grouped[namespace]
        print(f"Namespace: {namespace}")
        for project_key, usages in projects.items():
            print(f"  └── Project: {project_key}")
            for usage in usages:
                print(f"      ├── Scope: {usage['dependency_scope']}")
                if usage['parent_package_version_name']:
                    print(f"      └── Parent package version: {usage['parent_package_version_name']}")
                else:
                    print(f"      └── (No parent package version info)")
        print()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Search for dependencies and find which projects use them.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search_dependencies.py --dependencies "npm://lodash@4.17.21"
  python search_dependencies.py --dependencies "npm://react@18.2.0,maven://org.springframework:spring-core@5.3.21"
        """
    )
    parser.add_argument(
        '--dependencies', 
        type=str, 
        required=True, 
        help='Comma-separated list of dependencies in format: ecosystem://dependency@version'
    )
    args = parser.parse_args()
    
    # Parse dependencies
    dependency_strings = [dep.strip() for dep in args.dependencies.split(',')]
    dependencies = []
    
    for dep_str in dependency_strings:
        dep_info = parse_dependency(dep_str)
        if dep_info:
            dependencies.append(dep_info)
        else:
            print(f"Skipping invalid dependency: {dep_str}")
    
    if not dependencies:
        print("ERROR: No valid dependencies provided.")
        sys.exit(1)
    
    # Get environment values
    env = get_env_values()
    
    token_mgr = TokenManager(env["api_key"], env["api_secret"])
    
    # Search for each dependency
    all_results = {}
    
    for dep_info in dependencies:
        results = search_dependency_usage(token_mgr, env["initial_namespace"], dep_info)
        all_results[f"{dep_info['full_name']}@{dep_info['version']}"] = results
        
        # Display results for this dependency
        display_results(results, dep_info, env["initial_namespace"])
    
    # Generate output filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"dependency_search_results_{timestamp}.json"
    csv_filename = f"dependency_search_results_{timestamp}.csv"
    
    # Flatten results for CSV output (copy rows so JSON is not mutated)
    flat_results = []
    for dep_name, results in all_results.items():
        for result in results:
            flat_results.append({**result, "searched_dependency": dep_name})
    
    # Save results
    save_results_json(all_results, json_filename)
    save_results_csv(flat_results, csv_filename)
    
    # Summary
    total_usages = sum(len(results) for results in all_results.values())
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Dependencies searched: {len(dependencies)}")
    print(f"Total usages found: {total_usages}")
    print(f"Results saved to: {json_filename}, {csv_filename}")

if __name__ == "__main__":
    main()
