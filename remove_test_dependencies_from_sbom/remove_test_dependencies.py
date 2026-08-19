#!/usr/bin/env python3
"""
Script to download an SBOM in SPDX format and remove test/dev dependencies.
"""

import argparse
import json
import os
import sys
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

def create_spdx_sbom_export(namespace, token, package_version_uuids, project_name=None, output_format="FORMAT_JSON"):
    """
    Create an SPDX SBOM export including multiple packageVersions.
    """
    url = f"{API_URL}/namespaces/{namespace}/sbom-export"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600"
    }
    
    # Use project name if available, otherwise fall back to namespace
    sbom_name = project_name if project_name else f"{namespace}-sbom"
    
    payload = {
        "tenant_meta": {
            "namespace": namespace
        },
        "meta": {
            "name": f"SPDX SBOM Export: {sbom_name}"
        },
        "spec": {
            "kind": "SBOM_KIND_SPDX",
            "format": output_format,
            "component_type": "COMPONENT_TYPE_APPLICATION",
            "export_parameters": {
                "package_version_uuids": package_version_uuids
            }
        }
    }
    
    try:
        print(f"Creating SPDX SBOM export for {len(package_version_uuids)} packageVersions...")
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        
        sbom_data = response.json()
        return sbom_data
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to create SPDX SBOM export: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

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
                    import re
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

if __name__ == "__main__":
    main()
