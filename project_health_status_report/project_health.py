#!/usr/bin/env python3
"""
Script to query all projects in a namespace with project summaries and produce a CSV with basic project information,
including dependency resolution % and call graph %.
One project per row in the CSV.
"""

import csv
import json
import os
import sys
from typing import Dict, Any, List, Optional
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

def get_projects_with_summaries(namespace, token):
    """
    Query all projects in the namespace with project summaries using the queries API.
    
    Args:
        namespace: The namespace for the projects
        token: API authentication token
    
    Returns:
        List of dictionaries containing project information with summary metrics
    """
    url = f"{API_URL}/namespaces/{namespace}/queries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800"
    }
    
    base_payload: Dict[str, Any] = {
        "tenant_meta": {
            "namespace": namespace
        },
        "meta": {
            "name": "QueryProjectsWithSummaries"
        },
        "spec": {
            "query_spec": {
                "kind": "Project",
                "list_parameters": {
                    "page_size": 500,
                    "traverse": True,
                    "mask": "meta.name,meta.create_time,meta.update_time,spec.platform_source,tenant_meta.namespace,uuid"
                },
                "references": [
                    {
                        "connect_from": "uuid",
                        "connect_to": "meta.parent_uuid",
                        "query_spec": {
                            "kind": "ProjectSummary",
                            "list_parameters": {
                                "traverse": True,
                                "mask": "spec.automated_scan_enabled,spec.last_scanned,spec.package_coverage.total,spec.package_coverage.scan_failures,spec.package_coverage.success_rate,spec.package_coverage.call_graph_errors,spec.package_coverage.call_graph_available,spec.package_coverage.call_graph_success_rate,meta.name,uuid"
                            },
                            "return_as": "ProjectSummaryData"
                        }
                    },
                    {
                        "connect_from": "uuid",
                        "connect_to": "meta.parent_uuid",
                        "query_spec": {
                            "kind": "ScanResult",
                            "list_parameters": {
                                "filter": "context.type == CONTEXT_TYPE_MAIN and spec.environment.config.ScanConfig.Enables contains \"git\"",
                                "sort": {
                                    "path": "meta.create_time",
                                    "order": "SORT_ENTRY_ORDER_DESC"
                                },
                                "page_size": 1,
                                "mask": "uuid,meta.parent_uuid,meta.parent_kind,context.type,spec.start_time,spec.end_time,spec.stats,spec.runtimes,spec.environment.config,spec.environment.arch,spec.environment.os,spec.environment.memory,spec.environment.num_cpus,spec.environment.endorctl_version,spec.exit_code,spec.status",
                                "traverse": True
                            },
                            "return_as": "LatestScanResult"
                        }
                    }
                ]
            }
        }
    }
    
    combined_objects: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None
    page_count = 0
    
    print(f"Querying projects with summaries in namespace: {namespace}...")
    
    while True:
        page_count += 1
        # Create fresh payload per page and set/remove page_token as needed
        payload = json.loads(json.dumps(base_payload))  # deep copy
        lp = payload["spec"]["query_spec"]["list_parameters"]
        if next_page_token:
            lp["page_token"] = next_page_token
        elif "page_token" in lp:
            del lp["page_token"]
        
        try:
            print(f"Fetching projects page {page_count}...")
            response = requests.post(url, headers=headers, json=payload, timeout=1800)
            response.raise_for_status()
            
            data = response.json()
            # Queries API returns results under spec.query_response.list.objects
            query_response = data.get("spec", {}).get("query_response", {})
            objs = query_response.get("list", {}).get("objects", []) or []
            
            print(f"Received {len(objs)} projects on page {page_count}")
            combined_objects.extend(objs)
            
            # Check for next page token in the query response
            next_page_token = query_response.get("list", {}).get("response", {}).get("next_page_token")
            if not next_page_token:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to get projects: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return []
    
    print(f"Total projects found: {len(combined_objects)}")
    return combined_objects

def extract_project_info(project_obj):
    """
    Extract project information from the query result object.
    
    Args:
        project_obj: Project object from the query response
    
    Returns:
        Dictionary with project information
    """
    meta = project_obj.get('meta', {})
    spec = project_obj.get('spec', {})
    
    project_info = {
        'uuid': project_obj.get('uuid', ''),
        'name': meta.get('name', ''),
        'create_time': meta.get('create_time', ''),
        'update_time': meta.get('update_time', ''),
    }
    
    # Extract platform source
    if isinstance(spec, dict):
        project_info['platform_source'] = spec.get('platform_source', '')
    
    # Extract project summary data from references
    # References are in meta.references based on the response structure
    references = meta.get('references', {}) or project_obj.get('references', {})
    
    project_summary_data = references.get('ProjectSummaryData', {})
    
    # ProjectSummaryData is an object with a list.objects structure
    summary_list = project_summary_data.get('list', {}).get('objects', []) if isinstance(project_summary_data, dict) else []
    
    if summary_list and len(summary_list) > 0:
        summary = summary_list[0]
        summary_spec = summary.get('spec', {})
        package_coverage = summary_spec.get('package_coverage', {})
        
        # Extract package coverage metrics
        project_info['automated_scan_enabled'] = summary_spec.get('automated_scan_enabled', None)
        project_info['last_scanned'] = summary_spec.get('last_scanned', None)
        project_info['total_packages'] = package_coverage.get('total', None)
        project_info['scan_failures'] = package_coverage.get('scan_failures', None)
        
        # Convert decimals to percentages (multiply by 100)
        success_rate = package_coverage.get('success_rate', None)
        project_info['dependency_resolution_percentage'] = success_rate * 100 if success_rate is not None else None
        
        project_info['call_graph_errors'] = package_coverage.get('call_graph_errors', None)
        project_info['call_graph_available'] = package_coverage.get('call_graph_available', None)
        
        call_graph_success_rate = package_coverage.get('call_graph_success_rate', None)
        project_info['call_graph_percentage'] = call_graph_success_rate * 100 if call_graph_success_rate is not None else None
    else:
        project_info['automated_scan_enabled'] = None
        project_info['last_scanned'] = None
        project_info['total_packages'] = None
        project_info['scan_failures'] = None
        project_info['dependency_resolution_percentage'] = None
        project_info['call_graph_errors'] = None
        project_info['call_graph_available'] = None
        project_info['call_graph_percentage'] = None
    
    # Extract latest scan result data from references
    latest_scan_data = references.get('LatestScanResult', {})
    
    # LatestScanResult is an object with a list.objects structure
    scan_list = latest_scan_data.get('list', {}).get('objects', []) if isinstance(latest_scan_data, dict) else []
    
    if scan_list and len(scan_list) > 0:
        scan = scan_list[0]
        scan_spec = scan.get('spec', {})
        environment = scan_spec.get('environment', {})
        config = environment.get('config', {})
        
        project_info['endorctl_version'] = environment.get('endorctl_version', None)
        
        # Extract include_path and exclude_path from spec.environment.config.ScanConfig
        include_path = None
        exclude_path = None
        
        if isinstance(config, dict):
            scan_config = config.get('ScanConfig', {})
            if isinstance(scan_config, dict):
                include_path = scan_config.get('IncludePath')
                exclude_path = scan_config.get('ExcludePath')
                # Also try lowercase versions as fallback
                if include_path is None:
                    include_path = scan_config.get('include_path')
                if exclude_path is None:
                    exclude_path = scan_config.get('exclude_path')
        
        # Convert arrays to comma-separated strings if they are arrays
        # Handle both None and empty lists
        if include_path is not None:
            if isinstance(include_path, list):
                project_info['include_path'] = ','.join(str(p) for p in include_path) if include_path else ''
            else:
                project_info['include_path'] = include_path
        else:
            project_info['include_path'] = None
        
        if exclude_path is not None:
            if isinstance(exclude_path, list):
                project_info['exclude_path'] = ','.join(str(p) for p in exclude_path) if exclude_path else ''
            else:
                project_info['exclude_path'] = exclude_path
        else:
            project_info['exclude_path'] = None
    else:
        project_info['endorctl_version'] = None
        project_info['include_path'] = None
        project_info['exclude_path'] = None
    
    return project_info

def write_csv_file(filename, projects):
    """Write projects to a CSV file."""
    if not projects:
        # Create empty CSV with headers
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['uuid', 'name', 'create_time', 'update_time', 'platform_source', 
                            'automated_scan_enabled', 'last_scanned', 'total_packages', 'scan_failures', 
                            'dependency_resolution_percentage', 'call_graph_errors', 'call_graph_available', 
                            'call_graph_percentage', 'endorctl_version', 'include_path', 'exclude_path'])
        return
    
    # Determine all possible fieldnames from all projects
    fieldnames = set()
    for project in projects:
        fieldnames.update(project.keys())
    
    # Order fieldnames with common ones first
    ordered_fieldnames = ['uuid', 'name', 'create_time', 'update_time', 'platform_source', 
                          'automated_scan_enabled', 'last_scanned', 'total_packages', 'scan_failures', 
                          'dependency_resolution_percentage', 'call_graph_errors', 'call_graph_available', 
                          'call_graph_percentage', 'endorctl_version', 'include_path', 'exclude_path']
    # Add any additional fields that weren't in the ordered list
    for field in sorted(fieldnames):
        if field not in ordered_fieldnames:
            ordered_fieldnames.append(field)
    
    # Convert None values to empty strings for CSV output
    cleaned_projects = []
    for project in projects:
        cleaned_project = {}
        for field in ordered_fieldnames:
            value = project.get(field, None)
            cleaned_project[field] = '' if value is None else value
        cleaned_projects.append(cleaned_project)
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_projects)

def main():
    """Main function."""
    # Get environment values
    env = get_env_values()
    
    # Get API token
    token = get_token(env["api_key"], env["api_secret"])
    if not token:
        print("Failed to get API token.")
        sys.exit(1)
    
    # Use namespace from environment variable
    namespace = env["initial_namespace"]
    print(f"Using namespace: {namespace}")
    
    # Get all projects with summaries
    project_objects = get_projects_with_summaries(namespace, token)
    
    # Extract project information from query results
    projects = []
    for project_obj in project_objects:
        project_info = extract_project_info(project_obj)
        projects.append(project_info)
        print(f"Processed project: {project_info['name']} (UUID: {project_info['uuid']})")
    
    # Always write CSV file
    output_filename = 'projects.csv'
    write_csv_file(output_filename, projects)
    print(f"\nCSV file saved to: {output_filename}")
    print(f"Total projects: {len(projects)}")

if __name__ == "__main__":
    main()

