#!/usr/bin/env python3
"""
Script to download an SBOM in SPDX format and remove test/dev dependencies.
"""

import argparse
import json
import os
import re
import sys
import uuid
from collections import Counter
from urllib.parse import unquote
from datetime import datetime, timezone
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
    organization_name = os.getenv("ORGANIZATION_NAME")
    person_email = os.getenv("PERSON_EMAIL")
    
    if not api_key or not api_secret or not initial_namespace:
        print("ERROR: API_KEY, API_SECRET, and ENDOR_NAMESPACE environment variables must be set.")
        print("Please set them in a .env file or directly in your environment.")
        sys.exit(1)
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "initial_namespace": initial_namespace,
        "organization_name": organization_name,
        "person_email": person_email
    }

def get_token(api_key, api_secret):
    """Get API token using API key and secret."""
    url = f"{API_URL}/auth/api-key"
    payload = {
        "key": api_key,
        "secret": api_secret
    }
    headers = {
        "Content-Type": "application/json",
        "Request-Timeout": "60"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        response.raise_for_status()
        token = response.json().get('token')
        return token
    except requests.exceptions.RequestException as e:
        print(f"Failed to get token: {e}")
        sys.exit(1)

def get_project_details(token, project_uuid, initial_namespace):
    """
    Fetch project details and extract name and namespace.
    """
    url = f"{API_URL}/namespaces/{initial_namespace}/projects"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f"uuid=={project_uuid}",
        "list_parameters.mask": "meta.name,tenant_meta.namespace",
        "list_parameters.traverse": "true"
    }
    
    print(f"Fetching project details for project {project_uuid}...")
    
    try:
        print(f"Making request to: {url}")
        print(f"With params: {params}")
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        print(f"Response data keys: {list(data.keys())}")
        
        objects = data.get('list', {}).get('objects', [])
        print(f"Found {len(objects)} objects")
        
        if objects and len(objects) > 0:
            project_data = objects[0]
            print(f"Project data keys: {list(project_data.keys())}")
            print(f"Project data: {project_data}")
            
            project_name = project_data.get('meta', {}).get('name')
            namespace = project_data.get('tenant_meta', {}).get('namespace')
            
            print(f"Extracted project_name: {project_name}")
            print(f"Extracted namespace: {namespace}")
            
            if project_name and namespace:
                print(f"Project name: {project_name}, Namespace: {namespace}")
                return project_name, namespace
        
        print("Project details not found in response")
        return None, None
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get project details: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None, None

def get_default_branch(namespace, token, project_uuid):
    """Fetch the default branch name from the project's Repository object.

    Returns the value of spec.default_branch verbatim (e.g.
    'refs/heads/release/Sprint-200') or None if it can't be determined.
    """
    url = f"{API_URL}/namespaces/{namespace}/repositories"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    params = {
        "list_parameters.filter": f"meta.parent_uuid=={project_uuid}",
        "list_parameters.mask": "spec.default_branch",
        "list_parameters.traverse": "true"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        data = response.json()
        repos = data.get('list', {}).get('objects', [])
        if not repos:
            print(f"Warning: no Repository found for project {project_uuid}; default branch unknown")
            return None

        ref = repos[0].get('spec', {}).get('default_branch') or ''
        if not ref:
            print("Warning: Repository found but spec.default_branch is empty")
            return None

        print(f"Default branch for project: {ref}")
        return ref
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to fetch default branch: {e}")
        return None

def check_branch_context(namespace, token, project_uuid, branch):
    """
    Check if the project has only one repository version matching the branch.
    If so, use CONTEXT_TYPE_MAIN instead of context.id==branch.
    
    Returns:
        tuple: (use_main_context: bool, actual_branch_name: str or None)
    """
    url = f"{API_URL}/namespaces/{namespace}/repository-versions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f"meta.parent_uuid=={project_uuid}",
        "list_parameters.mask": "meta.name",
        "list_parameters.traverse": "true"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        repository_versions = data.get('list', {}).get('objects', [])
        
        print(f"Found {len(repository_versions)} repository versions for project {project_uuid}")
        
        # If only one repository version exists
        if len(repository_versions) == 1:
            repo_version = repository_versions[0]
            branch_name = repo_version.get('meta', {}).get('name', '')
            
            print(f"Single repository version found with name: {branch_name}")
            
            # If the single branch matches the passed branch name, use main context
            if branch_name == branch or branch_name == 'default':
                print(f"Project has only one branch ({branch_name}), using main context instead of branch-specific context")
                return True, branch_name
        
        # Check if any repository version matches the branch
        matching_branches = []
        for repo_version in repository_versions:
            branch_name = repo_version.get('meta', {}).get('name', '')
            if branch_name == branch:
                matching_branches.append(branch_name)
        
        if matching_branches:
            print(f"Found {len(matching_branches)} repository version(s) matching branch '{branch}'")
            return False, branch
        
        # If no matches found, still try the branch context (might be a new branch)
        print(f"No repository version found matching branch '{branch}', will try branch context anyway")
        return False, branch
        
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to check repository versions: {e}")
        print("Falling back to branch context")
        return False, branch

def resolve_use_main_context(namespace, token, project_uuid, branch, default_branch):
    """Decide whether to use CONTEXT_TYPE_MAIN or context.id==<branch>.

    - No --branch passed → main.
    - --branch matches the project's default branch → main.
    - --branch passed but default branch unknown → fall back to the single-branch
      heuristic in check_branch_context (preserves prior behavior on API errors).
    - Otherwise → branch context.
    """
    if not branch:
        return True
    if default_branch is not None:
        return branch == default_branch
    use_main, _ = check_branch_context(namespace, token, project_uuid, branch)
    return use_main

def get_package_versions(namespace, token, project_uuid, branch=None, default_branch=None):
    """Get all package versions for a project."""
    url = f"{API_URL}/namespaces/{namespace}/package-versions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }

    use_main_context = resolve_use_main_context(namespace, token, project_uuid, branch, default_branch)

    if use_main_context:
        context_filter = f"context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=={project_uuid}"
        if branch:
            print(f"Using main context (--branch {branch} matches default branch)")
        else:
            print("Using main context")
    else:
        context_filter = f"context.id=={branch} and spec.project_uuid=={project_uuid}"
        print(f"Using branch context: {branch}")
    
    params = {
        "list_parameters.filter": context_filter,
        "list_parameters.mask": "uuid,meta.name"
    }
    
    package_versions = []
    next_page_id = None
    
    print(f"Fetching packageVersions for project {project_uuid}...")
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id

        try:
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            
            response_data = response.json()
            items = response_data.get('list', {}).get('objects', [])
            
            for item in items:
                package_version = {
                    'uuid': item.get('uuid'),
                    'name': item.get('meta', {}).get('name', 'Unknown')
                }
                package_versions.append(package_version)
                print(f"Found packageVersion: {package_version['name']} (UUID: {package_version['uuid']})")

            next_page_id = response_data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to get packageVersions: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return []

    print(f"Total packageVersions found: {len(package_versions)}")
    return package_versions

def create_sbom_export(namespace, token, package_version_uuids, sbom_kind="SBOM_KIND_SPDX",
                       project_name=None, output_format="FORMAT_JSON"):
    """
    Create an SBOM export of the given kind covering multiple packageVersions.
    """
    url = f"{API_URL}/namespaces/{namespace}/sbom-export"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600"
    }
    
    label = "CycloneDX" if sbom_kind == "SBOM_KIND_CYCLONEDX" else "SPDX"

    # Use project name if available, otherwise fall back to namespace
    sbom_name = project_name if project_name else f"{namespace}-sbom"
    
    payload = {
        "tenant_meta": {
            "namespace": namespace
        },
        "meta": {
            "name": f"{label} SBOM Export: {sbom_name}"
        },
        "spec": {
            "kind": sbom_kind,
            "format": output_format,
            "component_type": "COMPONENT_TYPE_APPLICATION",
            "export_parameters": {
                "package_version_uuids": package_version_uuids
            }
        }
    }
    
    try:
        print(f"Creating {label} SBOM export for {len(package_version_uuids)} packageVersions...")
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        
        sbom_data = response.json()
        return sbom_data
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to create {label} SBOM export: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def create_spdx_sbom_export(namespace, token, package_version_uuids, project_name=None, output_format="FORMAT_JSON"):
    """Create an SPDX SBOM export including multiple packageVersions."""
    return create_sbom_export(namespace, token, package_version_uuids,
                              "SBOM_KIND_SPDX", project_name, output_format)


def _purl_key(purl):
    """Normalize a purl so the two exports join even when escaping differs."""
    return unquote(str(purl or "")).strip().lower()


def fetch_cyclonedx_enrichment(namespace, token, package_version_uuids, project_name=None):
    """Collect licenses and repository URLs from the CycloneDX export of the same packages.

    The SPDX export leaves licenseConcluded, licenseDeclared and downloadLocation
    as NOASSERTION, but the CycloneDX export of the very same packageVersions
    carries both. Returns a lookup keyed by purl and by "name@version"; an empty
    dict means the export failed and nothing will be filled in.
    """
    response = create_sbom_export(namespace, token, package_version_uuids,
                                  "SBOM_KIND_CYCLONEDX", project_name)
    if not response:
        print("Warning: CycloneDX export failed; NOASSERTION values will be left alone.")
        return {}

    content = response.get('spec', {}).get('data')
    try:
        data = json.loads(content) if isinstance(content, str) else (content or {})
    except json.JSONDecodeError:
        print("Warning: could not parse the CycloneDX export; NOASSERTION values left alone.")
        return {}

    lookup = {}
    with_license = 0
    components = data.get("components", [])
    for component in components:
        licenses = []
        for entry in component.get("licenses", []):
            if "expression" in entry:
                value = entry.get("expression")
            else:
                license_obj = entry.get("license", {})
                value = license_obj.get("id") or license_obj.get("name")
            if value:
                licenses.append(str(value))

        repository_url = None
        for ref in component.get("externalReferences", []):
            if ref.get("url") and ref.get("type") in ("vcs", "distribution"):
                repository_url = ref["url"]
                if ref.get("type") == "vcs":
                    break

        if not licenses and not repository_url:
            continue

        if licenses:
            with_license += 1

        record = {"licenses": licenses, "repository_url": repository_url}
        if component.get("purl"):
            lookup[_purl_key(component["purl"])] = record
        name, version = component.get("name"), component.get("version")
        if name and version:
            lookup.setdefault(f"{name}@{version}".lower(), record)

    print(f"CycloneDX export: {len(components)} components, "
          f"{with_license} carrying license data")
    return lookup


# Endor's public namespace, where it records analysis of OSS package versions.
OSS_NAMESPACE = "oss"
LICENSE_METRIC_NAME = "pkg_version_info_for_license"
API_BATCH_SIZE = 100

# SPDX defines supplier as the organization providing the package, and for an OSS
# dependency that is the registry it was fetched from. The purl names that
# registry outright, so this is a fact about the package rather than a guess.
REGISTRY_SUPPLIERS = {
    "npm": "npmjs.com",
    "nuget": "nuget.org",
    "maven": "repo.maven.apache.org",
    "golang": "proxy.golang.org",
    "pypi": "pypi.org",
    "cargo": "crates.io",
    "gem": "rubygems.org",
    "composer": "packagist.org",
    "cocoapods": "cocoapods.org",
    "conan": "conan.io",
    "cran": "cran.r-project.org",
    "hackage": "hackage.haskell.org",
    "hex": "hex.pm",
    "pub": "pub.dev",
    "swift": "swiftpackageindex.com",
    "github": "github.com",
    "githubactions": "github.com",
    "docker": "docker.io",
    "oci": "docker.io",
}


def _endor_package_name(purl):
    """Convert a purl into the name Endor uses, e.g. npm://lodash@4.17.21."""
    text = unquote(str(purl or ""))
    if not text.startswith("pkg:") or "/" not in text:
        return None
    ecosystem, rest = text[len("pkg:"):].split("/", 1)
    return f"{ecosystem}://{rest}" if ecosystem and rest else None


def _list_resource(namespace, token, resource, filter_expression, mask, page_size=500):
    """Run a single list query against the Endor API and return the objects."""
    url = f"{API_URL}/namespaces/{namespace}/{resource}"
    headers = {"Authorization": f"Bearer {token}", "Request-Timeout": "600"}
    params = {
        "list_parameters.filter": filter_expression,
        "list_parameters.mask": mask,
        "list_parameters.page_size": page_size,
    }
    response = requests.get(url, headers=headers, params=params, timeout=600)
    response.raise_for_status()
    return response.json().get("list", {}).get("objects", [])


def _extract_copyrights(value):
    """Pull copyright notices out of a metric value.

    They sit at metric_values -> licenseInfoType -> license_info -> copyrights,
    but the walk is defensive so a reshaped metric keeps working.
    """
    if isinstance(value, dict):
        notices = value.get("copyrights")
        if isinstance(notices, list) and notices:
            return [str(n).strip() for n in notices if str(n).strip()]
        for nested in value.values():
            found = _extract_copyrights(nested)
            if found:
                return found
    return []


def fetch_copyright_data(token, purls):
    """Look up copyright notices for OSS packages in Endor's public namespace.

    Endor records the copyright notices it finds in a package's source on the
    pkg_version_info_for_license metric, but the SBOM export does not carry them,
    so copyrightText arrives as NOASSERTION for every package. Returns a lookup
    of purl key -> newline-joined notices; an empty dict means none were found.
    """
    names = {}
    for purl in purls:
        name = _endor_package_name(purl)
        if name:
            names.setdefault(name, _purl_key(purl))
    if not names:
        return {}

    name_list = list(names)
    uuid_to_key = {}
    try:
        for start in range(0, len(name_list), API_BATCH_SIZE):
            batch = name_list[start:start + API_BATCH_SIZE]
            for obj in _list_resource(OSS_NAMESPACE, token, "package-versions",
                                      "meta.name in [" + ",".join(batch) + "]",
                                      "uuid,meta.name"):
                key = names.get(obj.get("meta", {}).get("name"))
                if key and obj.get("uuid"):
                    uuid_to_key[obj["uuid"]] = key
    except requests.exceptions.RequestException as e:
        print(f"Warning: could not resolve packages for the copyright lookup: {e}")
        return {}

    if not uuid_to_key:
        print("No matching OSS package versions found; copyright notices unavailable.")
        return {}

    copyrights = {}
    uuids = list(uuid_to_key)
    try:
        for start in range(0, len(uuids), API_BATCH_SIZE):
            batch = uuids[start:start + API_BATCH_SIZE]
            for obj in _list_resource(
                    OSS_NAMESPACE, token, "metrics",
                    f"meta.name=={LICENSE_METRIC_NAME} and meta.parent_uuid in ["
                    + ",".join(batch) + "]",
                    "meta.parent_uuid,spec.metric_values"):
                key = uuid_to_key.get(obj.get("meta", {}).get("parent_uuid"))
                if not key:
                    continue
                for value in (obj.get("spec", {}).get("metric_values") or {}).values():
                    notices = _extract_copyrights(value)
                    if notices:
                        # dict.fromkeys de-duplicates while keeping the order.
                        copyrights[key] = "\n".join(dict.fromkeys(notices))
                        break
    except requests.exceptions.RequestException as e:
        print(f"Warning: could not fetch copyright metrics: {e}")
        return copyrights

    print(f"Copyright notices found for {len(copyrights)} of {len(names)} packages")
    return copyrights


def get_test_dependencies_from_api(namespace, token, project_uuid, branch=None, default_branch=None):
    """Query Endor Labs API to get test dependencies for a project."""
    url = f"{API_URL}/namespaces/{namespace}/dependency-metadata"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }

    use_main_context = resolve_use_main_context(namespace, token, project_uuid, branch, default_branch)

    if use_main_context:
        context_filter = f"context.type==CONTEXT_TYPE_MAIN and spec.importer_data.project_uuid=={project_uuid} and spec.dependency_data.scope==DEPENDENCY_SCOPE_TEST"
        if branch:
            print(f"Querying test dependencies for main context (--branch {branch} matches default branch)")
        else:
            print("Querying test dependencies for main context")
    else:
        context_filter = f"context.id=={branch} and spec.importer_data.project_uuid=={project_uuid} and spec.dependency_data.scope==DEPENDENCY_SCOPE_TEST"
        print(f"Querying test dependencies for branch context: {branch}")
    
    params = {
        "list_parameters.filter": context_filter,
        "list_parameters.mask": "meta.name,spec.dependency_data,spec.importer_data"
    }
    
    test_dependencies = set()
    next_page_id = None
    page_num = 1
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id
        
        try:
            print(f"Fetching test dependencies page {page_num}...")
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            
            data = response.json()
            objects = data.get('list', {}).get('objects', [])
            print(f"Received {len(objects)} dependencies on page {page_num}")
            
            for obj in objects:
                dep_data = obj.get('spec', {}).get('dependency_data', {})
                package_name = dep_data.get('package_name', '')
                resolved_version = dep_data.get('resolved_version', '')
                
                # Extract just the package name from format like "npm://merge"
                if package_name and '://' in package_name:
                    package_name = package_name.split('://')[-1]
                
                if package_name and resolved_version:
                    test_dep = f"{package_name}@{resolved_version}"
                    test_dependencies.add(test_dep)
                    print(f"Auto-detected test dependency: {test_dep}")
                elif package_name:
                    test_dependencies.add(package_name)
                    print(f"Auto-detected test dependency: {package_name}")
            
            next_page_id = data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
            
            page_num += 1
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to get test dependencies from API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return set()
    
    print(f"Total auto-detected test dependencies: {len(test_dependencies)}")
    return test_dependencies

def read_test_dependencies(filename):
    """Read test dependencies from a text file."""
    if not os.path.exists(filename):
        print(f"Warning: {filename} not found. No test dependencies will be removed.")
        return set()
    
    test_deps = set()
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    test_deps.add(line)
        print(f"Loaded {len(test_deps)} test dependencies from {filename}")
        return test_deps
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return set()

def is_test_dependency(package_name, package_version, test_dependencies):
    """Check if a package is a test dependency."""
    # Check exact name match first
    if package_name in test_dependencies:
        return True
    
    # Check name@version format if specified in test_dependencies
    name_version = f"{package_name}@{package_version}"
    if name_version in test_dependencies:
        return True
    
    return False

def remove_test_dependencies(spdx_sbom, test_dependencies, organization_name=None, person_email=None):
    """
    Remove test dependencies and their relationships from the SPDX SBOM.
    
    Args:
        spdx_sbom: The SPDX SBOM data as a JSON object
        test_dependencies: Set of test dependency names to remove
        organization_name: Optional organization name for creation info
        person_email: Optional person email for creation info
    
    Returns:
        Cleaned SPDX SBOM as a JSON object
    """
    if test_dependencies:
        print(f"Removing {len(test_dependencies)} test dependencies from SBOM...")
    else:
        print("No test dependencies to remove.")

    # Create a copy to avoid modifying the original
    cleaned_sbom = json.loads(json.dumps(spdx_sbom))

    # Track packages to remove
    packages_to_remove = set()

    # Identify packages that are test dependencies
    for package in cleaned_sbom.get("packages", []):
        package_name = package.get("name", "")
        package_version = package.get("versionInfo", "")
        if is_test_dependency(package_name, package_version, test_dependencies):
            packages_to_remove.add(package.get("SPDXID"))
            print(f"Removing dependency: {package_name}@{package_version} ({package.get('SPDXID')})")

    # Remove test dependency packages
    cleaned_sbom["packages"] = [
        package for package in cleaned_sbom.get("packages", [])
        if package.get("SPDXID") not in packages_to_remove
    ]

    print(f"Removed {len(packages_to_remove)} packages")

    # Clean up relationships
    if "relationships" in cleaned_sbom:
        # Remove relationships that involve removed packages
        cleaned_sbom["relationships"] = [
            rel for rel in cleaned_sbom.get("relationships", [])
            if (rel.get("spdxElementId") not in packages_to_remove and 
                rel.get("relatedSpdxElement") not in packages_to_remove)
        ]
        
        # Also remove relationships that reference non-existent packages
        existing_package_ids = {pkg.get("SPDXID") for pkg in cleaned_sbom.get("packages", [])}
        existing_package_ids.add("SPDXRef-DOCUMENT")  # Document always exists
        
        cleaned_sbom["relationships"] = [
            rel for rel in cleaned_sbom.get("relationships", [])
            if (rel.get("spdxElementId") in existing_package_ids and 
                rel.get("relatedSpdxElement") in existing_package_ids)
        ]
        
        print(f"Cleaned up relationships, remaining: {len(cleaned_sbom['relationships'])}")

    # documentDescribes points at packages too, so it has to lose the removed
    # ones as well -- otherwise the document references ids that aren't there.
    if "documentDescribes" in cleaned_sbom:
        remaining_ids = {pkg.get("SPDXID") for pkg in cleaned_sbom.get("packages", [])}
        described = [d for d in cleaned_sbom["documentDescribes"] if d in remaining_ids]
        stale = len(cleaned_sbom["documentDescribes"]) - len(described)
        cleaned_sbom["documentDescribes"] = described
        if stale:
            print(f"Removed {stale} stale documentDescribes entries")
    
    # Update document metadata
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cleaned_sbom["creationInfo"]["created"] = current_time
    
    # Add organization and person info if provided
    if organization_name or person_email:
        creators = cleaned_sbom["creationInfo"].get("creators", [])
        
        # Remove existing Organization and Person entries to avoid duplicates
        creators = [creator for creator in creators if not creator.startswith("Organization:") and not creator.startswith("Person:")]
        
        if organization_name:
            creators.append(f"Organization: {organization_name}")
        
        if person_email:
            creators.append(f"Person: {person_email}")
        
        cleaned_sbom["creationInfo"]["creators"] = creators
    
    return cleaned_sbom

# ---------------------------------------------------------------------------
# SPDX online tool compliance (--spdx-online-tool-validation)
#
# The SPDX Online Tool at https://tools.spdx.org/app/ validates uploads against
# the SPDX 2.3 spec. The sbom-export output trips several of its rules:
#   * SPDXIDs are derived from raw package names, so npm scopes ("@scope/pkg"),
#     Maven coordinates ("group:artifact") and Go module paths keep characters
#     the spec forbids -- only letters, numbers, "." and "-" are allowed.
#   * downloadLocation carries a Package URL ("pkg:npm/..."), which is not a
#     download location. The purl belongs in externalRefs instead.
#   * licenseConcluded/licenseDeclared can carry registry free text such as
#     "The Apache Software License, Version 2.0". That is not a license
#     expression, and it makes the validator fail while still parsing the file.
# ---------------------------------------------------------------------------

SPDX_LICENSE_LIST_URL = "https://spdx.org/licenses/licenses.json"
SPDX_EXCEPTION_LIST_URL = "https://spdx.org/licenses/exceptions.json"
SPDX_LICENSE_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".spdx_license_cache.json"
)

# Only consulted when the official list can be neither fetched nor read from
# cache. Anything outside it becomes a LicenseRef, which is still valid -- just
# less precise than the real identifier.
FALLBACK_LICENSE_IDS = {
    "0BSD", "AFL-2.1", "AGPL-3.0-only", "AGPL-3.0-or-later", "Apache-1.1",
    "Apache-2.0", "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-4-Clause",
    "BSL-1.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0", "CDDL-1.0",
    "CDDL-1.1", "CPL-1.0", "EPL-1.0", "EPL-2.0", "EUPL-1.2", "GPL-2.0-only",
    "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "ICU", "ISC",
    "JSON", "LGPL-2.0-only", "LGPL-2.1-only", "LGPL-2.1-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later", "MIT", "MIT-0", "MPL-1.1", "MPL-2.0",
    "MS-PL", "NTP", "OFL-1.1", "OpenSSL", "PHP-3.01", "PSF-2.0", "Python-2.0",
    "Ruby", "SSPL-1.0", "Unlicense", "UPL-1.0", "W3C", "WTFPL", "X11", "Zlib",
    "ZPL-2.1",
}

FALLBACK_EXCEPTION_IDS = {
    "Autoconf-exception-3.0", "Bison-exception-2.2", "Classpath-exception-2.0",
    "Font-exception-2.0", "GCC-exception-3.1", "LLVM-exception",
    "OpenJDK-assembly-exception-1.0",
}

# Free-text license names that package registries commonly emit, mapped onto the
# SPDX identifier they mean. Keys are lowercased with whitespace collapsed.
LICENSE_NAME_ALIASES = {
    "the apache software license, version 2.0": "Apache-2.0",
    "apache software license, version 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache license, version 2": "Apache-2.0",
    "apache license version 2.0": "Apache-2.0",
    "apache license v2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache public license 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache2": "Apache-2.0",
    "asl 2.0": "Apache-2.0",
    "the mit license": "MIT",
    "the mit license (mit)": "MIT",
    "mit license": "MIT",
    "bsd license": "BSD-3-Clause",
    "the bsd license": "BSD-3-Clause",
    "new bsd license": "BSD-3-Clause",
    "modified bsd license": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "bsd-3": "BSD-3-Clause",
    "3-clause bsd license": "BSD-3-Clause",
    "simplified bsd license": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "2-clause bsd license": "BSD-2-Clause",
    "the isc license": "ISC",
    "isc license": "ISC",
    "gnu general public license, version 2": "GPL-2.0-only",
    "gnu general public license v2.0": "GPL-2.0-only",
    "gnu general public license, version 3": "GPL-3.0-only",
    "gnu lesser general public license": "LGPL-2.1-only",
    "gnu lesser general public license, version 2.1": "LGPL-2.1-only",
    "gnu lesser general public license v3.0": "LGPL-3.0-only",
    "eclipse public license - v 1.0": "EPL-1.0",
    "eclipse public license 1.0": "EPL-1.0",
    "eclipse public license - v 2.0": "EPL-2.0",
    "eclipse public license 2.0": "EPL-2.0",
    "mozilla public license, version 2.0": "MPL-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "common development and distribution license 1.0": "CDDL-1.0",
    "microsoft public license": "MS-PL",
    "the unlicense": "Unlicense",
    "public domain": "CC0-1.0",
}

# SPDX 2.3 relationship vocabulary. Anything outside it is rewritten to OTHER.
SPDX_RELATIONSHIP_TYPES = {
    "AMENDS", "ANCESTOR_OF", "BUILD_DEPENDENCY_OF", "BUILD_TOOL_OF",
    "CONTAINED_BY", "CONTAINS", "COPY_OF", "DATA_FILE_OF", "DEPENDENCY_MANIFEST_OF",
    "DEPENDENCY_OF", "DEPENDS_ON", "DESCENDANT_OF", "DESCRIBED_BY", "DESCRIBES",
    "DEV_DEPENDENCY_OF", "DEV_TOOL_OF", "DISTRIBUTION_ARTIFACT", "DOCUMENTATION_OF",
    "DYNAMIC_LINK", "EXAMPLE_OF", "EXPANDED_FROM_ARCHIVE", "FILE_ADDED",
    "FILE_DELETED", "FILE_MODIFIED", "GENERATED_FROM", "GENERATES",
    "HAS_PREREQUISITE", "METAFILE_OF", "OPTIONAL_COMPONENT_OF",
    "OPTIONAL_DEPENDENCY_OF", "OTHER", "PACKAGE_OF", "PATCH_APPLIED", "PATCH_FOR",
    "PREREQUISITE_FOR", "PROVIDED_DEPENDENCY_OF", "REQUIREMENT_DESCRIPTION_FOR",
    "RUNTIME_DEPENDENCY_OF", "SPECIFICATION_FOR", "STATIC_LINK",
    "TEST_CASE_OF", "TEST_DEPENDENCY_OF", "TEST_OF", "TEST_TOOL_OF", "VARIANT_OF",
}

_SPDX_ID_RE = re.compile(r'^SPDXRef-[A-Za-z0-9.\-]+$')
_LICENSE_REF_RE = re.compile(r'^(?:DocumentRef-[A-Za-z0-9.\-]+:)?LicenseRef-[A-Za-z0-9.\-]+$')
_LICENSE_OPERATORS = {"AND", "OR", "WITH"}
# Mirrors the download location grammar in the SPDX spec (and in the reference
# validators): an optional scheme, an optional userinfo part, then a host that
# must carry a real dotted TLD -- so "https://deeplay-io/nice-grpc" is rejected.
_URL_PATTERN = (
    r"(http://www\.|https://www\.|http://|https://|ssh://|git://|svn://|sftp://|ftp://)?"
    r"([\w\-.!~*'()%;:&=+$,]+@)?[a-z0-9]+([\-.][a-z0-9]+){0,100}\.[a-z]{2,5}"
    r"(:[0-9]{1,5})?(/.*)?"
)
_URL_RE = re.compile(_URL_PATTERN, re.IGNORECASE)
_DOWNLOAD_LOCATION_RE = re.compile(
    r"^(((git|hg|svn|bzr)\+)?" + _URL_PATTERN + r"|"
    r"(git\+git@[a-zA-Z0-9.\-]+:[a-zA-Z0-9/\\.@\-]+)|"
    r"(bzr\+lp:[a-zA-Z0-9.\-]+))$",
    re.IGNORECASE,
)
# An absolute URI with no fragment -- "urn:uuid:..." is as valid as "https://...".
_URI_RE = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*:[^\s#]+$')


def _is_valid_download_location(text):
    """Match the reference validator: a bare URL prefix or a full VCS location."""
    return bool(_URL_RE.match(text) or _DOWNLOAD_LOCATION_RE.match(text))
_ACTOR_RE = re.compile(r'^(?:Person|Organization):\s*\S')
_CREATOR_RE = re.compile(r'^(?:Person|Organization|Tool):\s*\S')
_TIMESTAMP_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')


def load_spdx_license_ids():
    """Return (license_ids, exception_ids) for validating license expressions.

    Reads the cached copy of the official SPDX license list if one is present,
    otherwise fetches it from spdx.org and caches it next to this script. Falls
    back to a small built-in set when the list is unreachable -- delete
    .spdx_license_cache.json to force a refresh.
    """
    if os.path.exists(SPDX_LICENSE_CACHE):
        try:
            with open(SPDX_LICENSE_CACHE, 'r') as f:
                cached = json.load(f)
            licenses = set(cached.get("licenses") or [])
            exceptions = set(cached.get("exceptions") or [])
            if licenses and exceptions:
                print(f"Using cached SPDX license list {cached.get('version', 'unknown')} "
                      f"({len(licenses)} licenses, {len(exceptions)} exceptions)")
                return licenses, exceptions
        except Exception as e:
            print(f"Warning: could not read {SPDX_LICENSE_CACHE}: {e}")

    try:
        print("Fetching the official SPDX license list from spdx.org...")
        lic_response = requests.get(SPDX_LICENSE_LIST_URL, timeout=60)
        lic_response.raise_for_status()
        lic_data = lic_response.json()

        exc_response = requests.get(SPDX_EXCEPTION_LIST_URL, timeout=60)
        exc_response.raise_for_status()
        exc_data = exc_response.json()

        licenses = {entry["licenseId"] for entry in lic_data.get("licenses", [])
                    if entry.get("licenseId")}
        exceptions = {entry["licenseExceptionId"] for entry in exc_data.get("exceptions", [])
                      if entry.get("licenseExceptionId")}
        version = lic_data.get("licenseListVersion", "unknown")

        if not licenses:
            raise ValueError("license list response contained no licenses")

        try:
            with open(SPDX_LICENSE_CACHE, 'w') as f:
                json.dump({"version": version,
                           "licenses": sorted(licenses),
                           "exceptions": sorted(exceptions)}, f)
        except Exception as e:
            print(f"Warning: could not write {SPDX_LICENSE_CACHE}: {e}")

        print(f"Loaded SPDX license list {version} "
              f"({len(licenses)} licenses, {len(exceptions)} exceptions)")
        return licenses, exceptions
    except Exception as e:
        print(f"Warning: could not fetch the SPDX license list: {e}")
        print("Falling back to the built-in list; licenses outside it become LicenseRef- entries.")
        return set(FALLBACK_LICENSE_IDS), set(FALLBACK_EXCEPTION_IDS)


def sanitize_spdx_id(raw_id, used_ids):
    """Return a spec-legal SPDXID, unique against used_ids.

    The spec allows only letters, numbers, "." and "-" after the "SPDXRef-"
    prefix, so npm scopes, Maven coordinates and module paths need rewriting.
    """
    text = str(raw_id or "")
    body = text[len("SPDXRef-"):] if text.startswith("SPDXRef-") else text
    body = re.sub(r'[^A-Za-z0-9.\-]', '-', body)
    body = re.sub(r'-{2,}', '-', body).strip('-.')
    if not body:
        body = "Package"

    candidate = f"SPDXRef-{body}"
    unique = candidate
    counter = 1
    while unique in used_ids:
        counter += 1
        unique = f"{candidate}-{counter}"
    used_ids.add(unique)
    return unique


def _license_expression_is_valid(expression, license_ids, exception_ids, known_refs):
    """Check an SPDX license expression against the license list.

    Walks the expression as operand/operator pairs so that adjacent identifiers
    without a joining operator are rejected the same way the validator does.
    """
    depth = 0
    for char in expression:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                return False
    if depth != 0:
        return False

    tokens = [t for t in re.split(r'[()\s]+', expression) if t]
    if not tokens:
        return False

    expect = 'operand'
    for token in tokens:
        if expect == 'operand':
            if token.upper() in _LICENSE_OPERATORS:
                return False
            base = token[:-1] if token.endswith('+') else token
            if base in license_ids:
                expect = 'operator'
                continue
            if _LICENSE_REF_RE.match(token) and token in known_refs:
                expect = 'operator'
                continue
            return False
        if expect == 'operator':
            # SPDX requires the operators themselves to be upper case.
            if token not in _LICENSE_OPERATORS:
                return False
            expect = 'exception' if token == 'WITH' else 'operand'
            continue
        if token not in exception_ids:
            return False
        expect = 'operator'
    return expect == 'operator'


class _LicenseNormalizer:
    """Rewrites license fields into expressions the SPDX validator accepts."""

    def __init__(self, license_ids, exception_ids, extracted_infos):
        self.license_ids = license_ids
        self.exception_ids = exception_ids
        self.ci_ids = {lid.lower(): lid for lid in license_ids}
        self.extracted = extracted_infos
        self.known_refs = {info.get("licenseId") for info in extracted_infos
                           if info.get("licenseId")}
        self.used_ref_ids = set(self.known_refs)
        self.by_text = {info.get("extractedText"): info.get("licenseId")
                        for info in extracted_infos if info.get("extractedText")}
        self.aliased = 0
        self.reffed = 0

    def _license_ref_for(self, text):
        """Mint (or reuse) a LicenseRef that preserves the original text."""
        if text in self.by_text:
            return self.by_text[text]

        slug = re.sub(r'[^A-Za-z0-9.\-]', '-', text)
        slug = re.sub(r'-{2,}', '-', slug).strip('-.')[:60]
        if not slug:
            slug = "Unknown"

        candidate = f"LicenseRef-{slug}"
        unique = candidate
        counter = 1
        while unique in self.used_ref_ids:
            counter += 1
            unique = f"{candidate}-{counter}"

        self.used_ref_ids.add(unique)
        self.known_refs.add(unique)
        self.by_text[text] = unique
        self.extracted.append({
            "licenseId": unique,
            "extractedText": text,
            "name": text,
        })
        self.reffed += 1
        return unique

    def normalize(self, value):
        text = " ".join(str(value).split()) if value is not None else ""
        if not text:
            return "NOASSERTION"
        if text in ("NOASSERTION", "NONE"):
            return text
        if _license_expression_is_valid(text, self.license_ids,
                                        self.exception_ids, self.known_refs):
            return text

        # Try the spelling as-is, then without a leading "The ", which is the
        # only thing separating a lot of registry names from the alias table.
        lowered = text.lower()
        for key in (lowered, re.sub(r'^the\s+', '', lowered)):
            alias = LICENSE_NAME_ALIASES.get(key)
            if alias and alias in self.license_ids:
                self.aliased += 1
                return alias

        # "apache-2.0" and "MIT " differ from the canonical spelling only in case.
        canonical = self.ci_ids.get(text.lower())
        if canonical:
            self.aliased += 1
            return canonical

        return self._license_ref_for(text)


def _ensure_purl_external_ref(package, purl):
    """Record a Package URL where SPDX expects it -- externalRefs."""
    refs = package.setdefault("externalRefs", [])
    for ref in refs:
        if ref.get("referenceType") == "purl" and ref.get("referenceLocator") == purl:
            return
    refs.append({
        "referenceCategory": "PACKAGE-MANAGER",
        "referenceType": "purl",
        "referenceLocator": purl,
    })


def _fix_download_location(package, stats):
    """downloadLocation must be NONE, NOASSERTION, a URL or a VCS location."""
    raw = package.get("downloadLocation")
    text = str(raw).strip() if raw is not None else ""

    if text in ("NONE", "NOASSERTION"):
        return
    if text and _is_valid_download_location(text):
        return

    if text.startswith("pkg:"):
        _ensure_purl_external_ref(package, text)
        stats["purls_moved_to_external_refs"] += 1
    elif text:
        # Park the unusable value in sourceInfo rather than dropping it silently.
        note = f"Original downloadLocation: {text}"
        existing = str(package.get("sourceInfo") or "").strip()
        if note not in existing:
            package["sourceInfo"] = f"{existing}\n{note}" if existing else note
        stats["download_locations_moved_to_source_info"] += 1
    else:
        stats["download_locations_filled_in"] += 1

    package["downloadLocation"] = "NOASSERTION"


def _fix_actor_field(package, field, stats):
    """supplier/originator must be NOASSERTION or a Person:/Organization: entry."""
    if field not in package:
        return
    text = " ".join(str(package[field]).split())
    if text == "NOASSERTION" or _ACTOR_RE.match(text):
        package[field] = text
        return
    package[field] = "NOASSERTION"
    stats[f"{field}_fields_reset"] += 1


def _is_unset(value):
    """True when a field carries no actual information."""
    return str(value or "").strip() in ("", "NOASSERTION", "NONE")


def _lookup_enrichment(package, enrichment):
    """Find a package's CycloneDX record, by purl first and then name@version."""
    if not enrichment:
        return None

    location = str(package.get("downloadLocation") or "")
    if location.startswith("pkg:"):
        record = enrichment.get(_purl_key(location))
        if record:
            return record

    for ref in package.get("externalRefs", []):
        if ref.get("referenceType") == "purl":
            record = enrichment.get(_purl_key(ref.get("referenceLocator")))
            if record:
                return record

    name, version = package.get("name"), package.get("versionInfo")
    if name and version:
        return enrichment.get(f"{name}@{version}".lower())
    return None


def _fill_licenses_from_record(package, record, stats):
    """Fill license fields that assert nothing. Real values are never overwritten."""
    licenses = record.get("licenses") or []
    if not licenses:
        return

    if len(licenses) == 1:
        expression = licenses[0]
    else:
        # Several declared licenses means all of them apply. Parenthesize any
        # entry that is itself an expression so the AND binds the way it reads.
        expression = " AND ".join(f"({item})" if " " in item else item
                                  for item in licenses)

    filled = False
    for field in ("licenseConcluded", "licenseDeclared"):
        if _is_unset(package.get(field)):
            package[field] = expression
            filled = True
    if filled:
        stats["licenses_filled_from_cyclonedx"] += 1


def _fill_download_location_from_record(package, record, stats):
    """Use the repository URL when the export supplied no download location."""
    url = record.get("repository_url")
    if not url or not _is_unset(package.get("downloadLocation")):
        return
    if _is_valid_download_location(str(url)):
        package["downloadLocation"] = str(url)
        stats["download_locations_filled_from_cyclonedx"] += 1


def _purl_type(package):
    """The purl ecosystem for a package, or None when it carries no purl."""
    locators = [ref.get("referenceLocator") for ref in package.get("externalRefs", [])
                if ref.get("referenceType") == "purl"]
    locators.append(package.get("downloadLocation"))
    for locator in locators:
        text = unquote(str(locator or ""))
        if text.startswith("pkg:") and "/" in text:
            return text[len("pkg:"):].split("/", 1)[0].lower()
    return None


def _package_purl_key(package):
    """The normalized purl for a package, for joining against API lookups."""
    for ref in package.get("externalRefs", []):
        if ref.get("referenceType") == "purl" and ref.get("referenceLocator"):
            return _purl_key(ref["referenceLocator"])
    location = str(package.get("downloadLocation") or "")
    return _purl_key(location) if location.startswith("pkg:") else None


def _fill_supplier_from_registry(package, stats):
    """Name the registry that supplied the package when nothing else is known."""
    if not _is_unset(package.get("supplier")):
        return
    registry = REGISTRY_SUPPLIERS.get(_purl_type(package))
    if not registry:
        return
    package["supplier"] = f"Organization: {registry}"
    stats["suppliers_set_to_registry"] += 1


def _fill_root_package(doc, root_version, stats):
    """Complete the package the document describes -- the application itself.

    Its supplier is the organization configured in Endor's SBOM settings, which
    the export records in creationInfo.creators rather than on the package that
    the conformance checker actually reads.
    """
    described = set(doc.get("documentDescribes") or [])
    for relationship in doc.get("relationships", []):
        kind = relationship.get("relationshipType")
        if kind == "DESCRIBES" and relationship.get("spdxElementId") == "SPDXRef-DOCUMENT":
            described.add(relationship.get("relatedSpdxElement"))
        elif kind == "DESCRIBED_BY" and relationship.get("relatedSpdxElement") == "SPDXRef-DOCUMENT":
            described.add(relationship.get("spdxElementId"))
    if not described:
        return

    organization = next((c for c in doc.get("creationInfo", {}).get("creators", [])
                         if str(c).startswith("Organization: ")), None)

    for package in doc.get("packages", []):
        if package.get("SPDXID") not in described:
            continue
        # OSS dependencies carry a purl; the application does not.
        if _purl_type(package):
            continue
        if organization and _is_unset(package.get("supplier")):
            package["supplier"] = organization
            stats["root_supplier_from_sbom_settings"] += 1
        if root_version and not str(package.get("versionInfo") or "").strip():
            package["versionInfo"] = root_version
            stats["root_versions_filled"] += 1


def make_spdx_online_tool_compliant(spdx_sbom, enrichment=None, copyrights=None,
                                    root_version=None):
    """Rewrite an SPDX document so https://tools.spdx.org/app/ accepts it.

    When `enrichment` holds CycloneDX data from fetch_cyclonedx_enrichment, any
    license or download location the SPDX export left as NOASSERTION is filled
    in from it. `copyrights` from fetch_copyright_data does the same for
    copyrightText, and every package still missing a supplier is attributed to
    the registry that distributed it. Fields that already carry a real value are
    never overwritten.

    Returns (document, stats). The input is left untouched.
    """
    print("Applying SPDX online tool compliance fixes...")
    doc = json.loads(json.dumps(spdx_sbom))
    stats = Counter()

    license_ids, exception_ids = load_spdx_license_ids()

    # --- document level ------------------------------------------------------
    if doc.get("spdxVersion") not in ("SPDX-2.2", "SPDX-2.3"):
        doc["spdxVersion"] = "SPDX-2.3"
        stats["document_fields_fixed"] += 1
    if doc.get("dataLicense") != "CC0-1.0":
        doc["dataLicense"] = "CC0-1.0"
        stats["document_fields_fixed"] += 1
    if doc.get("SPDXID") != "SPDXRef-DOCUMENT":
        doc["SPDXID"] = "SPDXRef-DOCUMENT"
        stats["document_fields_fixed"] += 1
    if not str(doc.get("name") or "").strip():
        doc["name"] = "SPDX Document"
        stats["document_fields_fixed"] += 1

    namespace = str(doc.get("documentNamespace") or "").strip()
    if '#' in namespace:
        namespace = namespace.split('#', 1)[0]
    if not _URI_RE.match(namespace):
        namespace = f"https://endorlabs.com/spdx/documents/{uuid.uuid4()}"
    if namespace != doc.get("documentNamespace"):
        doc["documentNamespace"] = namespace
        stats["document_fields_fixed"] += 1

    creation_info = doc.setdefault("creationInfo", {})
    creators = [" ".join(str(c).split()) for c in creation_info.get("creators", [])
                if isinstance(c, str)]
    valid_creators = [c for c in creators if _CREATOR_RE.match(c)]
    if len(valid_creators) != len(creators):
        stats["creators_dropped"] += len(creators) - len(valid_creators)
    if not valid_creators:
        valid_creators = ["Tool: endorlabs-remove-test-dependencies"]
        stats["document_fields_fixed"] += 1
    creation_info["creators"] = valid_creators
    if not _TIMESTAMP_RE.match(str(creation_info.get("created") or "")):
        creation_info["created"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stats["document_fields_fixed"] += 1

    # --- extracted licensing info -------------------------------------------
    extracted = [info for info in doc.get("hasExtractedLicensingInfos", [])
                 if isinstance(info, dict)]
    for info in extracted:
        license_id = str(info.get("licenseId") or "")
        if not _LICENSE_REF_RE.match(license_id):
            slug = re.sub(r'[^A-Za-z0-9.\-]', '-', license_id.replace("LicenseRef-", ""))
            slug = re.sub(r'-{2,}', '-', slug).strip('-.') or "Unknown"
            info["licenseId"] = f"LicenseRef-{slug}"
            stats["extracted_license_ids_fixed"] += 1
        if not str(info.get("extractedText") or "").strip():
            info["extractedText"] = info.get("name") or info["licenseId"]
            stats["extracted_license_ids_fixed"] += 1
    normalizer = _LicenseNormalizer(license_ids, exception_ids, extracted)

    # --- SPDXID remapping ----------------------------------------------------
    # Reserve the document id, then rewrite every element id that breaks the
    # charset rule, keeping a map so references can follow.
    used_ids = {"SPDXRef-DOCUMENT"}
    id_map = {}

    def remap(element):
        original = element.get("SPDXID")
        if original in used_ids or not _SPDX_ID_RE.match(str(original or "")):
            new_id = sanitize_spdx_id(original, used_ids)
            if new_id != original:
                stats["spdx_ids_rewritten"] += 1
            element["SPDXID"] = new_id
        else:
            used_ids.add(original)
            new_id = original
        if original is not None and original not in id_map:
            id_map[original] = new_id

    for package in doc.get("packages", []):
        remap(package)
    for spdx_file in doc.get("files", []):
        remap(spdx_file)
    for snippet in doc.get("snippets", []):
        remap(snippet)

    def resolve(reference):
        """Map an old id onto its rewritten form, or None if it no longer exists."""
        if reference in ("SPDXRef-DOCUMENT", "NONE", "NOASSERTION"):
            return reference
        mapped = id_map.get(reference, reference)
        return mapped if mapped in used_ids else None

    # --- packages ------------------------------------------------------------
    for package in doc.get("packages", []):
        # Look the package up before the purl moves out of downloadLocation,
        # then fill the download location once _fix_download_location has run.
        record = _lookup_enrichment(package, enrichment)
        purl_key = _package_purl_key(package)
        if record:
            _fill_licenses_from_record(package, record, stats)
        _fix_download_location(package, stats)
        if record:
            _fill_download_location_from_record(package, record, stats)
        _fix_actor_field(package, "supplier", stats)
        _fix_actor_field(package, "originator", stats)
        # Attribute the package after the actor fields are normalized, so a
        # malformed supplier that was just reset also gets a registry.
        _fill_supplier_from_registry(package, stats)

        notices = (copyrights or {}).get(purl_key)
        if notices and _is_unset(package.get("copyrightText")):
            package["copyrightText"] = notices
            stats["copyright_notices_filled"] += 1

        for field in ("licenseConcluded", "licenseDeclared"):
            if field in package:
                fixed = normalizer.normalize(package[field])
                if fixed != package[field]:
                    stats["license_fields_fixed"] += 1
                package[field] = fixed

        if "licenseInfoFromFiles" in package:
            package["licenseInfoFromFiles"] = [normalizer.normalize(v)
                                               for v in package["licenseInfoFromFiles"]]
        if not str(package.get("copyrightText") or "").strip():
            package["copyrightText"] = "NOASSERTION"

        if "hasFiles" in package:
            kept = [r for r in (resolve(f) for f in package["hasFiles"]) if r]
            package["hasFiles"] = kept
        # No file list means no file analysis, and saying so keeps the validator
        # from demanding a packageVerificationCode.
        if not package.get("hasFiles") and "packageVerificationCode" not in package:
            if package.get("filesAnalyzed") is not False:
                package["filesAnalyzed"] = False
                stats["files_analyzed_set_false"] += 1
            package.pop("hasFiles", None)

    for spdx_file in doc.get("files", []):
        for field in ("licenseConcluded",):
            if field in spdx_file:
                spdx_file[field] = normalizer.normalize(spdx_file[field])
        if "licenseInfoInFiles" in spdx_file:
            spdx_file["licenseInfoInFiles"] = [normalizer.normalize(v)
                                               for v in spdx_file["licenseInfoInFiles"]]
        if not str(spdx_file.get("copyrightText") or "").strip():
            spdx_file["copyrightText"] = "NOASSERTION"

    # --- references ----------------------------------------------------------
    if "documentDescribes" in doc:
        described = [r for r in (resolve(d) for d in doc["documentDescribes"]) if r]
        dropped = len(doc["documentDescribes"]) - len(described)
        if dropped:
            stats["document_describes_dropped"] += dropped
        doc["documentDescribes"] = described

    if "relationships" in doc:
        kept_relationships = []
        for relationship in doc["relationships"]:
            source = resolve(relationship.get("spdxElementId"))
            target = resolve(relationship.get("relatedSpdxElement"))
            if not source or not target:
                stats["relationships_dropped"] += 1
                continue
            relationship["spdxElementId"] = source
            relationship["relatedSpdxElement"] = target
            if relationship.get("relationshipType") not in SPDX_RELATIONSHIP_TYPES:
                relationship["relationshipType"] = "OTHER"
                stats["relationship_types_fixed"] += 1
            kept_relationships.append(relationship)
        doc["relationships"] = kept_relationships

    # A document holding more than one package must state what it describes.
    packages = doc.get("packages", [])
    single_package_only = (len(packages) == 1 and not doc.get("files")
                           and not doc.get("snippets"))
    if packages and not single_package_only:
        relationships = doc.setdefault("relationships", [])
        has_describes = any(
            (r.get("relationshipType") == "DESCRIBES"
             and r.get("spdxElementId") == "SPDXRef-DOCUMENT")
            or (r.get("relationshipType") == "DESCRIBED_BY"
                and r.get("relatedSpdxElement") == "SPDXRef-DOCUMENT")
            for r in relationships
        )
        if not has_describes:
            described = doc.get("documentDescribes") or [p.get("SPDXID") for p in packages]
            for spdx_id in described:
                relationships.append({
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "relatedSpdxElement": spdx_id,
                    "relationshipType": "DESCRIBES",
                })
            stats["describes_relationships_added"] += len(described)

    _fill_root_package(doc, root_version, stats)

    if extracted:
        doc["hasExtractedLicensingInfos"] = extracted
    stats["licenses_mapped_to_spdx_ids"] += normalizer.aliased
    stats["licenses_converted_to_license_refs"] += normalizer.reffed

    if stats:
        print("SPDX compliance changes:")
        for key in sorted(stats):
            print(f"  {key.replace('_', ' ')}: {stats[key]}")
    else:
        print("SPDX compliance: no changes needed.")

    return doc, stats


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Download SPDX SBOM and remove test dependencies.')
    parser.add_argument('--project_uuid', type=str, required=True, help='The UUID of the project')
    parser.add_argument('--output', type=str, help='Output SPDX file name (defaults to {project_uuid}-cleaned-spdx.json)')
    parser.add_argument('--branch', type=str, help='Branch context to analyze (defaults to main context)')
    parser.add_argument('--auto-remove-test-deps', action='store_true', 
                       help='Automatically detect and remove test dependencies from Endor Labs API')
    parser.add_argument('--test-deps-file', type=str, default='test_dependencies.txt', 
                       help='File containing test dependencies to remove (default: test_dependencies.txt)')
    parser.add_argument('--organization', type=str, help='Organization name for SBOM creation info')
    parser.add_argument('--person-email', type=str, help='Person email for SBOM creation info')
    parser.add_argument('--spdx-online-tool-validation', action='store_true',
                       help='Rewrite the cleaned SBOM so it validates at https://tools.spdx.org/app/')
    
    args = parser.parse_args()

    # Validate that user specified at least one removal method
    if not args.auto_remove_test_deps and '--test-deps-file' not in sys.argv:
        print("ERROR: You must specify either --auto-remove-test-deps or --test-deps-file")
        print("Usage examples:")
        print("  python remove_test_dependencies.py --project_uuid <uuid> --auto-remove-test-deps")
        print("  python remove_test_dependencies.py --project_uuid <uuid> --test-deps-file my_deps.txt")
        print("  python remove_test_dependencies.py --project_uuid <uuid> --auto-remove-test-deps --test-deps-file my_deps.txt")
        sys.exit(1)
    
    # Set default filenames based on project_uuid and branch if not provided.
    # Branch names can contain '/' (e.g. 'refs/heads/release/Sprint-200'), which
    # would be interpreted as directory separators in the output path — replace
    # them with '_' for the filename only; API calls still use the raw value.
    if not args.output:
        if args.branch:
            safe_branch = args.branch.replace('/', '_')
            args.output = f"{args.project_uuid}-{safe_branch}-cleaned-spdx.json"
        else:
            args.output = f"{args.project_uuid}-cleaned-spdx.json"
    
    # Get environment values
    env = get_env_values()
    
    # Get API token
    token = get_token(env["api_key"], env["api_secret"])
    if not token:
        print("Failed to get API token.")
        sys.exit(1)
    
    # Determine final organization name and person email with fallback logic
    final_organization_name = None
    final_person_email = None
    
    # Priority: Command line args -> Environment variables -> Will be extracted from original SBOM
    if args.organization:
        final_organization_name = args.organization
        print(f"Using organization from command line: {final_organization_name}")
    elif env.get("organization_name"):
        final_organization_name = env["organization_name"]
        print(f"Using organization from environment: {final_organization_name}")
    
    if args.person_email:
        final_person_email = args.person_email
        print(f"Using person email from command line: {final_person_email}")
    elif env.get("person_email"):
        final_person_email = env["person_email"]
        print(f"Using person email from environment: {final_person_email}")
    
    # Get project details using the initial namespace from .env
    project_name, namespace = get_project_details(token, args.project_uuid, env["initial_namespace"])
    
    if not namespace:
        print(f"ERROR: Could not determine namespace for project {args.project_uuid}.")
        sys.exit(1)
    
    print(f"Using namespace from project details: {namespace}")

    # Fetch the project's default branch from its Repository object so we can
    # treat --branch <default> the same as no --branch (use CONTEXT_TYPE_MAIN).
    default_branch = get_default_branch(namespace, token, args.project_uuid)

    # First, get all packageVersions for the project
    package_versions = get_package_versions(namespace, token, args.project_uuid, args.branch, default_branch)
    
    if not package_versions:
        print(f"No packageVersions found for project {args.project_uuid}.")
        sys.exit(1)
    
    # Extract just the UUIDs from the package_versions list
    package_version_uuids = [pv['uuid'] for pv in package_versions]
    
    # Generate an SPDX SBOM with all package versions
    spdx_response = create_spdx_sbom_export(namespace, token, package_version_uuids, project_name, "FORMAT_JSON")
    
    if not spdx_response:
        print("Failed to generate SPDX SBOM.")
        sys.exit(1)
    
    # Extract SPDX data
    spdx_data = None
    spdx_content = spdx_response.get('spec', {}).get('data')
    
    if spdx_content:
        try:
            spdx_data = json.loads(spdx_content)
        except json.JSONDecodeError:
            print("Error: Failed to parse SPDX data")
            sys.exit(1)
    else:
        print("Warning: No SPDX data found at spec.data path")
        # Try to use the response directly if it has packages
        if 'packages' in spdx_response:
            spdx_data = spdx_response
    
    if not spdx_data:
        print("Failed to process SPDX data.")
        sys.exit(1)
    
    # Extract organization/person info from original SBOM if not already set
    original_creators = spdx_data.get("creationInfo", {}).get("creators", [])
    for creator in original_creators:
        if creator.startswith("Organization:") and not final_organization_name:
            final_organization_name = creator.replace("Organization: ", "")
            print(f"Extracted organization from original SBOM: {final_organization_name}")
        elif creator.startswith("Person:") and not final_person_email:
            # Handle both "Person: email@domain.com" and "Person: Name (email@domain.com)" formats
            person_info = creator.replace("Person: ", "")
            if '@' in person_info:
                # Extract email from "Name (email@domain.com)" format
                if '(' in person_info and ')' in person_info:
                    email_match = re.search(r'\(([^)]+)\)', person_info)
                    if email_match:
                        final_person_email = email_match.group(1)
                    else:
                        final_person_email = person_info
                else:
                    final_person_email = person_info
                print(f"Extracted person email from original SBOM: {final_person_email}")
                # Break to ensure we only take the first Person entry found
                if final_person_email:
                    break
    
    # Read test dependencies from file only if user explicitly specified --test-deps-file
    if '--test-deps-file' in sys.argv:
        test_dependencies = read_test_dependencies(args.test_deps_file)
    else:
        test_dependencies = set()
    
    # Get auto-detected test dependencies from API if requested
    if args.auto_remove_test_deps:
        api_test_deps = get_test_dependencies_from_api(namespace, token, args.project_uuid, args.branch, default_branch)
        # Combine API-detected and manually specified test dependencies
        all_test_deps = api_test_deps.union(test_dependencies)
        print(f"Combined {len(api_test_deps)} auto-detected + {len(test_dependencies)} manual test dependencies")
    else:
        all_test_deps = test_dependencies
        print(f"Using {len(test_dependencies)} manual test dependencies")
    
    # Remove test dependencies
    cleaned_spdx = remove_test_dependencies(spdx_data, all_test_deps, 
                                           final_organization_name, 
                                           final_person_email)

    # Rewrite the cleaned SBOM so https://tools.spdx.org/app/ accepts the upload.
    # The original SBOM is left exactly as the API returned it.
    if args.spdx_online_tool_validation:
        enrichment = fetch_cyclonedx_enrichment(namespace, token,
                                                package_version_uuids, project_name)
        purls = [key for key in (_package_purl_key(pkg)
                                 for pkg in cleaned_spdx.get("packages", [])) if key]
        copyrights = fetch_copyright_data(token, purls)

        # The application's own version: Endor supplies none for the root
        # component, so fall back to the ref that was analyzed.
        root_version = args.branch or default_branch or ""
        if root_version.startswith("refs/heads/"):
            root_version = root_version[len("refs/heads/"):]

        cleaned_spdx, _ = make_spdx_online_tool_compliant(
            cleaned_spdx, enrichment, copyrights, root_version or None)
    
    # Save the original SPDX SBOM
    original_output = args.output.replace('-cleaned-', '-original-')
    with open(original_output, 'w') as f:
        json.dump(spdx_data, f, indent=2)
    
    # Save the cleaned SPDX SBOM
    with open(args.output, 'w') as f:
        json.dump(cleaned_spdx, f, indent=2)
    
    print(f"SBOM processing complete!")
    print(f"Original SBOM saved to: {original_output}")
    print(f"Cleaned SBOM saved to: {args.output}")
    print(f"Original packages: {len(spdx_data.get('packages', []))}")
    print(f"Cleaned packages: {len(cleaned_spdx.get('packages', []))}")
    print(f"Removed packages: {len(spdx_data.get('packages', [])) - len(cleaned_spdx.get('packages', []))}")
    if args.spdx_online_tool_validation:
        print(f"Upload {args.output} to https://tools.spdx.org/app/validate/ to confirm.")

if __name__ == "__main__":
    main()
