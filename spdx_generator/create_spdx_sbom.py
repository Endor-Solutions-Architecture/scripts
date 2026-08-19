#!/usr/bin/env python3
"""
Script to create a SPDX SBOM from CycloneDX format using the Endor Labs API.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
import re

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = 'https://api.endorlabs.com/v1'

# Default values for SPDX required fields
DEFAULT_VALUES = {
    "supplier_name": "NOASSERTION",
    "component_name": "Unknown Component",
    "component_version": "0.0.0",
    "sbom_author": "Endor Labs Customer Solutions SPDX Generator"
}

def get_env_values():
    """Get necessary values from environment variables."""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    organization = os.getenv("ORGANIZATION")
    person_email = os.getenv("PERSON_EMAIL")
    initial_namespace = os.getenv("ENDOR_NAMESPACE")
    
    if not api_key or not api_secret or not initial_namespace:
        print("ERROR: API_KEY, API_SECRET, and ENDOR_NAMESPACE environment variables must be set.")
        print("Please set them in a .env file or directly in your environment.")
        sys.exit(1)
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "organization": organization,
        "person_email": person_email,
        "initial_namespace": initial_namespace
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
    
    Args:
        token: The API token
        project_uuid: The UUID of the project
        initial_namespace: The initial namespace from .env
    
    Returns:
        Tuple containing (project_name, namespace)
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
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        objects = data.get('list', {}).get('objects', [])
        
        if objects and len(objects) > 0:
            project_data = objects[0]
            project_name = project_data.get('meta', {}).get('name')
            namespace = project_data.get('tenant_meta', {}).get('namespace')
            
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

def get_package_versions(namespace, token, project_uuid):
    url = f"{API_URL}/namespaces/{namespace}/package-versions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f"context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=={project_uuid}",
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

def create_cyclonedx_sbom_export(namespace, token, package_version_uuids, output_format="FORMAT_JSON"):
    """
    Create a CycloneDX SBOM export including multiple packageVersions.
    
    Args:
        namespace: The namespace to use
        token: The API token
        package_version_uuids: List of packageVersion UUIDs to include
        output_format: The output format (FORMAT_JSON or FORMAT_XML)
    
    Returns:
        The SBOM data if successful, None otherwise
    """
    url = f"{API_URL}/namespaces/{namespace}/sbom-export"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600"
    }
    
    payload = {
        "tenant_meta": {
            "namespace": namespace
        },
        "meta": {
            "name": f"SBOM Export: {namespace}-sbom"
        },
        "spec": {
            "kind": "SBOM_KIND_CYCLONEDX",
            "format": output_format,
            "component_type": "COMPONENT_TYPE_APPLICATION",
            "export_parameters": {
                "package_version_uuids": package_version_uuids
            }
        }
    }
    
    try:
        print(f"SBOM export for {len(package_version_uuids)} packageVersions...")
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        
        sbom_data = response.json()
        return sbom_data
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to create SBOM export: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def get_package_version_by_name(token, dependency_name):
    url = f"{API_URL}/namespaces/oss/package-versions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f'context.type==CONTEXT_TYPE_MAIN and meta.name=="{dependency_name}"',
        "list_parameters.mask": "uuid,meta.name"
    }
    
    try:
        print(f"Looking up package version for {dependency_name}...")
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        objects = data.get('list', {}).get('objects', [])
        
        if objects and len(objects) > 0:
            return objects[0]
        else:
            print(f"No package version found for {dependency_name}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Failed to get package version for {dependency_name}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def get_dependency_metadata(namespace, token, project_uuid):
    """
    Fetch dependency metadata filtered by project_uuid.
    
    Args:
        namespace: The namespace to use
        token: The API token
        project_uuid: The UUID of the project to filter dependencies
    
    Returns:
        Dictionary containing dependency relationships
    """
    url = f"{API_URL}/namespaces/{namespace}/dependency-metadata"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f"context.type==CONTEXT_TYPE_MAIN and spec.importer_data.project_uuid=={project_uuid}",
        "list_parameters.mask": "meta.name,spec.dependency_data,spec.importer_data"
    }
    
    print(f"Fetching dependency metadata for project {project_uuid}...")
    
    # Structure to hold all dependencies
    dependencies = []
    direct_dependencies = set()
    package_name_to_deps = {}
    
    next_page_id = None
    page_num = 1
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id
        
        try:
            print(f"Fetching page {page_num} of dependency metadata...")
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            
            data = response.json()
            objects = data.get('list', {}).get('objects', [])
            print(f"Received {len(objects)} dependencies on page {page_num}")
            
            # Process objects from this page
            for obj in objects:
                meta = obj.get('meta', {})
                dep_data = obj.get('spec', {}).get('dependency_data', {})
                
                # Get the package name and the resolved version
                package_name = dep_data.get('package_name', '')
                resolved_version = dep_data.get('resolved_version', '')
                full_name = meta.get('name', '')  # Should be in format like "pypi://requests@2.32.3"
                
                # Check if this is a direct dependency
                is_direct = dep_data.get('direct', False)
                
                # Get parent package name
                parent_name = dep_data.get('parent_version_name', '')
                
                # Store dependency information
                dependency_info = {
                    'name': full_name,
                    'package_name': package_name,
                    'version': resolved_version,
                    'is_direct': is_direct,
                    'parent': parent_name
                }
                
                dependencies.append(dependency_info)
                
                if is_direct:
                    direct_dependencies.add(full_name)
                
                # Build a mapping from parent package to its dependencies
                if parent_name:
                    if parent_name not in package_name_to_deps:
                        package_name_to_deps[parent_name] = []
                    package_name_to_deps[parent_name].append(full_name)
            
            # Check if there's another page
            next_page_id = data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
            
            page_num += 1
            print(f"Next Page ID: {next_page_id}")
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get dependency metadata on page {page_num}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            break
    
    result = {
        'dependencies': dependencies,
        'direct_dependencies': direct_dependencies,
        'package_name_to_deps': package_name_to_deps
    }
    
    print(f"Fetched {len(dependencies)} total dependencies, {len(direct_dependencies)} are direct dependencies")
    return result

def get_project_name(namespace, token, project_uuid):
    url = f"{API_URL}/namespaces/{namespace}/projects"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    params = {
        "list_parameters.filter": f"uuid=={project_uuid}",
        "list_parameters.mask": "meta.name",
        "list_parameters.traverse": "true"
    }
    
    print(f"Fetching project name for project {project_uuid}...")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        objects = data.get('list', {}).get('objects', [])
        
        if objects and len(objects) > 0:
            project_data = objects[0]
            project_name = project_data.get('meta', {}).get('name')
            
            if project_name:
                print(f"Project name: {project_name}")
                return project_name
        
        print("Project name not found in response")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get project name: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Create a SPDX SBOM using the Endor Labs API.')
    parser.add_argument('--project_uuid', type=str, required=True, help='The UUID of the project')
    parser.add_argument('--output', type=str, help='Output SPDX file name (defaults to {project_uuid}-spdx.json)')
    parser.add_argument('--format', type=str, choices=['json', 'xml'], default='json', help='Output format (json or xml)')
    
    args = parser.parse_args()
    
    # Set default filenames based on project_uuid if not provided
    if not args.output:
        args.output = f"{args.project_uuid}-spdx.json"
    
    # Get environment values
    env = get_env_values()
    
    # Get API token
    token = get_token(env["api_key"], env["api_secret"])
    if not token:
        print("Failed to get API token.")
        sys.exit(1)
    
    # Get project details using the initial namespace from .env
    project_name, namespace = get_project_details(token, args.project_uuid, env["initial_namespace"])
    
    if not namespace:
        print(f"ERROR: Could not determine namespace for project {args.project_uuid}.")
        sys.exit(1)
    
    print(f"Using namespace from project details: {namespace}")
    
    # Map format argument to API value
    output_format = f"FORMAT_{args.format.upper()}"
    
    # First, get all packageVersions for the project
    package_versions = get_package_versions(namespace, token, args.project_uuid)
    
    if not package_versions:
        print(f"No packageVersions found for project {args.project_uuid}.")
        sys.exit(1)
    
    # Extract just the UUIDs from the package_versions list
    package_version_uuids = [pv['uuid'] for pv in package_versions]
    
    # Get dependency metadata
    dependency_metadata = get_dependency_metadata(namespace, token, args.project_uuid)
    
    # Generate a CycloneDX SBOM with all package versions
    cyclonedx_response = create_cyclonedx_sbom_export(namespace, token, package_version_uuids, output_format)
    
    if not cyclonedx_response:
        print("Failed to generate CycloneDX SBOM.")
        sys.exit(1)
    
    # Extract CycloneDX data without saving to file
    cyclonedx_data = None
    cyclonedx_content = cyclonedx_response.get('spec', {}).get('data')
    
    if cyclonedx_content:
        try:
            cyclonedx_data = json.loads(cyclonedx_content)
        except json.JSONDecodeError:
            print("Error: Failed to parse CycloneDX data")
            sys.exit(1)
    else:
        print("Warning: No CycloneDX data found at spec.data path")
        # Try to use the response directly if it has components
        if 'components' in cyclonedx_response:
            cyclonedx_data = cyclonedx_response
    
    # Convert to SPDX format
    if cyclonedx_data:
        spdx_data = convert_cyclonedx_to_spdx(cyclonedx_data, namespace, args.project_uuid, 
                                             env["organization"], env["person_email"], dependency_metadata, project_name)
        
        if spdx_data:
            # Save the SPDX SBOM
            with open(args.output, 'w') as f:
                json.dump(spdx_data, f, indent=2)
            print(f"SPDX SBOM generation complete. Saved to {args.output}")
        else:
            print("Failed to convert to SPDX format.")
            sys.exit(1)
    else:
        print("Failed to process CycloneDX data.")
        sys.exit(1)

def convert_cyclonedx_to_spdx(cyclonedx_sbom, namespace, project_uuid, organization, person_email, dependency_metadata=None, project_name=None):
    """
    Convert CycloneDX SBOM to SPDX format, ensuring all minimum required fields are present.
    
    Args:
        cyclonedx_sbom: The CycloneDX SBOM data as a JSON object
        namespace: The namespace for the project
        project_uuid: The UUID of the project
        organization: The organization name
        person_email: The email of the person creating the SBOM
        dependency_metadata: Dependency metadata from the API
        project_name: Project name from the API
    
    Returns:
        SPDX SBOM as a JSON object
    """
    print("Creating SBOM in SPDX format...")
    
    # Create a new SPDX document
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    document_uuid = str(uuid.uuid4())
    
    # Create a single application ID that will be referenced in documentDescribes
    # Use the same UUID for both document and application to maintain linkage
    application_uuid = f"{project_uuid}-{document_uuid}"
    application_spdx_id = f"SPDXRef-Application-{application_uuid}"
    
    # Use project name if available, otherwise use a default
    display_name = project_name if project_name else f"{namespace} Application"
    
    spdx_sbom = {
        "SPDXID": "SPDXRef-DOCUMENT",
        "spdxVersion": "SPDX-2.3",
        "creationInfo": {
            "created": current_time,
            "creators": [
                f"Organization: {organization}",
                "Tool: Endor Labs CS tool",
                f"Person: {person_email}"
            ]
        },
        "name": f"SBOM for {display_name} ({project_uuid})",
        "dataLicense": "CC0-1.0",
        "documentNamespace": f"https://api.endorlabs.com/spdx/documents/{document_uuid}",
        "documentDescribes": [application_spdx_id],
        "packages": []
    }
    
    # Add packages from CycloneDX components
    if isinstance(cyclonedx_sbom, str):
        try:
            cyclonedx_data = json.loads(cyclonedx_sbom)
        except json.JSONDecodeError:
            print("Error: Failed to parse CycloneDX JSON data")
            return None
    else:
        cyclonedx_data = cyclonedx_sbom
        
    # Extract components from the CycloneDX SBOM
    components = cyclonedx_data.get("components", [])
    if not components and "metadata" in cyclonedx_data and "component" in cyclonedx_data["metadata"]:
        # Some CycloneDX SBOMs have components inside metadata.component.components
        components = cyclonedx_data["metadata"]["component"].get("components", [])
        
    if not components:
        print("Warning: No components found in CycloneDX SBOM")
    
    # Track relationships
    relationships = []
    
    # Create mappings for easier relationship building
    name_to_spdxid = {}
    used_spdx_ids = set()  # Track used SPDX IDs to prevent duplicates
    
    # First, create the main application package that will be described by the document
    main_app_package = {
        "SPDXID": application_spdx_id,
        "name": f"{namespace} Application",
        "versionInfo": "1.0.0",
        "supplier": f"Organization: {organization}",
        "downloadLocation": "NOASSERTION",
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION"
    }
    spdx_sbom["packages"].append(main_app_package)
    used_spdx_ids.add(application_spdx_id)  # Track the main application SPDX ID
    
    # Create DESCRIBES relationship between document and main application
    relationships.append({
        "spdxElementId": "SPDXRef-DOCUMENT",
        "relatedSpdxElement": application_spdx_id,
        "relationshipType": "DESCRIBES"
    })
    
    # Map each component to an SPDX package
    for component in components:
        component_name = component.get("name", DEFAULT_VALUES["component_name"])
        component_version = component.get("version", DEFAULT_VALUES["component_version"])
        supplier_name = component.get("supplier", {}).get("name", DEFAULT_VALUES["supplier_name"])
        if not supplier_name and "publisher" in component:
            supplier_name = component.get("publisher", DEFAULT_VALUES["supplier_name"])
        
        # Extract URL from externalReferences if available
        download_location = "NOASSERTION"
        if "externalReferences" in component:
            for ref in component.get("externalReferences", []):
                if ref.get("type") in ["vcs", "distribution"]:
                    download_location = ref.get("url", "NOASSERTION")
                    break
        else:
            download_location = component.get("purl", "NOASSERTION")
        
        # Create a unique SPDX identifier for this package
        spdx_id = generate_unique_spdx_id(component_name, component_version, used_spdx_ids)
        
        # Build the full package name with version for mapping
        full_package_name = f"{component_name}@{component_version}"
        
        # Store the mappings
        name_to_spdxid[full_package_name] = spdx_id
        
        # Create the SPDX package with minimum required fields
        package = {
            "SPDXID": spdx_id,
            "name": component_name,
            "versionInfo": component_version,
            "supplier": f"Organization: {supplier_name}",
            "downloadLocation": download_location,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION"
        }
        
        # Handle license information
        licenses = component.get("licenses", [])
        if licenses:
            license_ids = []
            for license_info in licenses:
                license_id = None
                if "license" in license_info:
                    # Try to get the license ID or name
                    license_obj = license_info["license"]
                    license_id = license_obj.get("id") or license_obj.get("name")
                elif "expression" in license_info:
                    license_id = license_info["expression"]
                
                if license_id:
                    license_ids.append(license_id)
            
            if license_ids:
                package["licenseConcluded"] = " AND ".join(license_ids)
                package["licenseDeclared"] = " AND ".join(license_ids)
        
        # Add the package to the SPDX document
        spdx_sbom["packages"].append(package)
    
    # Process dependency relationships from the API if available
    if dependency_metadata:
        already_processed = set()
        unique_deps = set()  # Track unique dependencies
        
        direct_deps = dependency_metadata.get('direct_dependencies', set())
        deps_list = dependency_metadata.get('dependencies', [])
        package_to_deps = dependency_metadata.get('package_name_to_deps', {})
        
        # Create a mapping from package names in dependency metadata to SPDX IDs
        api_name_to_spdxid = {}
        for dep_info in deps_list:
            full_name = dep_info.get('name', '')
            unique_deps.add(full_name)  # Add to unique set
            # Extract just the name and version from format like "pypi://requests@2.32.3"
            if '@' in full_name:
                parts = full_name.split('@')
                name_part = parts[0].split('://')[-1] if '://' in parts[0] else parts[0]
                version = parts[1]
                
                component_key = f"{name_part}@{version}"
                if component_key in name_to_spdxid:
                    api_name_to_spdxid[full_name] = name_to_spdxid[component_key]
        
        print(f"Total unique dependencies found: {len(unique_deps)}")  # Print the count
        
        # First, add direct dependencies from main application to direct dependencies
        for dep_name in direct_deps:
            if dep_name in api_name_to_spdxid:
                dep_spdxid = api_name_to_spdxid[dep_name]
                
                # Add DEPENDS_ON relationship
                relationships.append({
                    "spdxElementId": application_spdx_id,
                    "relatedSpdxElement": dep_spdxid,
                    "relationshipType": "DEPENDS_ON"
                })
                
                # Add inverse DEPENDENCY_OF relationship
                relationships.append({
                    "spdxElementId": dep_spdxid,
                    "relatedSpdxElement": application_spdx_id,
                    "relationshipType": "DEPENDENCY_OF"
                })
        
        # Then add transitive dependencies between packages
        for parent_name, deps in package_to_deps.items():
            if parent_name in api_name_to_spdxid:
                parent_spdxid = api_name_to_spdxid[parent_name]
                
                for dep_name in deps:
                    if dep_name in api_name_to_spdxid:
                        dep_spdxid = api_name_to_spdxid[dep_name]
                        
                        # Create a unique key for this relationship to avoid duplicates
                        rel_key = f"{parent_spdxid}:{dep_spdxid}"
                        if rel_key in already_processed:
                            continue
                        
                        # Add DEPENDS_ON relationship
                        relationships.append({
                            "spdxElementId": parent_spdxid,
                            "relatedSpdxElement": dep_spdxid,
                            "relationshipType": "DEPENDS_ON"
                        })
                        
                        # Add inverse DEPENDENCY_OF relationship
                        relationships.append({
                            "spdxElementId": dep_spdxid,
                            "relatedSpdxElement": parent_spdxid,
                            "relationshipType": "DEPENDENCY_OF"
                        })
                        
                        already_processed.add(rel_key)
    
    # Add the relationships to the SPDX document
    spdx_sbom["relationships"] = relationships
    
    return spdx_sbom

def generate_unique_spdx_id(component_name, component_version, used_ids):
    """
    Generate a unique SPDX ID for a component, handling duplicates and special characters.
    
    Args:
        component_name: The name of the component
        component_version: The version of the component  
        used_ids: Set of already used SPDX IDs
    
    Returns:
        A unique SPDX ID string
    """
    # Sanitize the component name - replace all non-alphanumeric chars with hyphens
    sanitized_name = re.sub(r'[^a-zA-Z0-9]', '-', component_name)
    # Remove multiple consecutive hyphens
    sanitized_name = re.sub(r'-+', '-', sanitized_name)
    # Remove leading/trailing hyphens
    sanitized_name = sanitized_name.strip('-')
    
    # Sanitize version similarly
    sanitized_version = ""
    if component_version:
        sanitized_version = re.sub(r'[^a-zA-Z0-9]', '-', str(component_version))
        sanitized_version = re.sub(r'-+', '-', sanitized_version)
        sanitized_version = sanitized_version.strip('-')
    
    # Create base SPDX ID
    if sanitized_version:
        base_id = f"SPDXRef-Package-{sanitized_name}-{sanitized_version}"
    else:
        base_id = f"SPDXRef-Package-{sanitized_name}"
    
    # Ensure uniqueness by adding counter if needed
    unique_id = base_id
    counter = 1
    while unique_id in used_ids:
        unique_id = f"{base_id}-{counter}"
        counter += 1
    
    used_ids.add(unique_id)
    return unique_id

if __name__ == "__main__":
    main() 