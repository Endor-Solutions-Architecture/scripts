#!/usr/bin/env python3
"""
Script to export all dependencies from all projects.
"""

import argparse
import json
import os
import sys
import csv
from datetime import datetime
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = 'https://api.endorlabs.com/v1'

def get_env_values():
    """Get necessary values from environment variables."""
    # Check if .env file exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_file):
        print("WARNING: .env file not found. Looking for environment variables...")
    
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    initial_namespace = os.getenv("ENDOR_NAMESPACE")
    
    if not api_key or not api_secret or not initial_namespace:
        print("ERROR: API_KEY, API_SECRET, and ENDOR_NAMESPACE environment variables must be set.")
        print("Please set them in a .env file or directly in your environment.")
        if not os.path.exists(env_file):
            print(f"\nTo create a .env file:")
            print(f"1. Copy env_template to .env: cp env_template .env")
            print(f"2. Edit .env and add your actual credentials")
        sys.exit(1)
    
    # Verify credentials are not placeholder values
    if api_key == "<YOUR_KEY>" or api_secret == "<YOUR_SECRET>" or initial_namespace == "<YOUR_TENANT_NAMESPACE>":
        print("ERROR: Please replace the placeholder values in your .env file with actual credentials.")
        sys.exit(1)
    
    print(f"Loaded credentials for namespace: {initial_namespace}")
    print(f"API Key: {'*' * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else '****'}")
    
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
        print("Authenticating with Endor Labs API...")
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        response.raise_for_status()
        token = response.json().get('token')
        if not token:
            print("ERROR: Authentication succeeded but no token was returned.")
            sys.exit(1)
        print("Authentication successful!")
        return token
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"ERROR: Authentication failed (401 Unauthorized)")
            print("This usually means:")
            print("  1. Your API_KEY or API_SECRET is incorrect")
            print("  2. Your API key has expired")
            print("  3. Your API key doesn't have the required permissions")
            print("\nTo fix this:")
            print("  1. Verify your credentials in the Endor Labs UI")
            print("  2. Generate a new API key if needed")
            print("  3. Ensure the API key has access to the namespace you're trying to use")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"\nAPI Error Details: {error_detail}")
                except:
                    print(f"\nResponse: {e.response.text}")
        else:
            print(f"ERROR: HTTP {e.response.status_code}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"Error Details: {error_detail}")
                except:
                    print(f"Response: {e.response.text}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to connect to Endor Labs API: {e}")
        print("Please check your internet connection and try again.")
        sys.exit(1)


def export_all_dependencies(token, initial_namespace):
    """Export all dependencies from all projects using QUERY API."""
    print(f"\nExporting all dependencies from all projects...")
    
    url = f"{API_URL}/namespaces/{initial_namespace}/queries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": "600"
    }
    
    # Build query payload for DependencyMetadata with grouping
    # Group by dependency name and version, and get unique project UUIDs per group
    query_payload = {
        "meta": {
            "name": "All Dependencies Grouped"
        },
        "spec": {
            "query_spec": {
                "kind": "DependencyMetadata",
                "list_parameters": {
                    "filter": "context.type==CONTEXT_TYPE_MAIN",
                    "mask": "meta.name,spec.dependency_data,spec.importer_data",
                    "traverse": True,
                    "group_by_field": {
                        "aggregation_paths": [
                            "spec.dependency_data.package_name",
                            "spec.dependency_data.resolved_version"
                        ],
                        "show_aggregation_uuids": True,
                        "unique_values": {
                            "paths": [
                                "spec.importer_data.project_uuid",
                                "tenant_meta.namespace"
                            ]
                        }
                    }
                }
            }
        }
    }
    
    # Get grouped results
    print("Fetching grouped dependencies...")
    try:
        response = requests.post(url, headers=headers, json=query_payload, timeout=600)
        response.raise_for_status()
        data = response.json()
        
        # Extract groups from QUERY API response structure
        query_response = data.get('spec', {}).get('query_response', {})
        group_response = query_response.get('group_response', {})
        groups = group_response.get('groups', {})
        
        print(f"Found {len(groups)} unique dependency groups")
        
        # Process groups to build results
        all_results = []
        group_num = 1
        
        for group_key, group_data in groups.items():
            # Parse the group key to get dependency name and version
            # Group key format: "[{\"key\":\"spec.dependency_data.package_name\",\"value\":\"npm://lodash\"},{\"key\":\"spec.dependency_data.resolved_version\",\"value\":\"4.17.21\"}]"
            try:
                import json as json_module
                group_keys = json_module.loads(group_key)
                dep_name = None
                dep_version = None
                for key_obj in group_keys:
                    if key_obj.get('key') == 'spec.dependency_data.package_name':
                        dep_name = key_obj.get('value')
                    elif key_obj.get('key') == 'spec.dependency_data.resolved_version':
                        dep_version = key_obj.get('value')
                
                if not dep_name or not dep_version:
                    continue
                
                aggregation_count = group_data.get('aggregation_count', {}).get('count', 0)
                unique_values = group_data.get('unique_values', {})
                
                # Get unique project UUIDs and namespaces from unique_values
                project_uuids = unique_values.get('spec.importer_data.project_uuid', [])
                namespaces = unique_values.get('tenant_meta.namespace', [])
                
                print(f"Group {group_num}/{len(groups)}: {dep_name}@{dep_version} ({aggregation_count} occurrences, {len(project_uuids)} unique projects)")
                
                # Create a result entry for each project UUID
                # Note: We're using unique values, so if a project uses the same dependency multiple times,
                # it will only appear once per group
                # We'll use the first available namespace (namespaces are aggregated in deduplication)
                namespace = namespaces[0] if namespaces else initial_namespace
                
                for project_uuid in project_uuids:
                    if project_uuid:  # Skip empty UUIDs
                        result = {
                            'namespace': namespace,
                            'project_uuid': project_uuid,
                            'dependency_name': dep_name,
                            'dependency_version': dep_version,
                            'dependency_scope': '',  # Not available from grouping
                            'parent_package_version_name': ''  # Not available from grouping
                        }
                        all_results.append(result)
                
                group_num += 1
                
            except Exception as e:
                print(f"Error processing group {group_key}: {e}")
                continue
        
        print(f"\nProcessed {len(all_results)} dependency-project combinations from {len(groups)} unique dependencies")
        return all_results
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to export dependencies: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return []

def deduplicate_dependencies(results):
    """Remove duplicates based on dependency name and version, aggregating project information."""
    if not results:
        return results
    
    # Dictionary to store unique dependencies: key = (dependency_name, dependency_version)
    unique_deps = {}
    
    for result in results:
        dep_key = (result.get('dependency_name', ''), result.get('dependency_version', ''))
        
        if dep_key not in unique_deps:
            # First occurrence - create new entry
            unique_deps[dep_key] = {
                'dependency_name': result.get('dependency_name', ''),
                'dependency_version': result.get('dependency_version', ''),
                'dependency_scope': result.get('dependency_scope', ''),
                'parent_package_version_name': result.get('parent_package_version_name', ''),
                'namespaces': set([result.get('namespace', '')]),
                'projects': set(),  # Will store project UUIDs
            }
        
        # Aggregate project information
        project_uuid = result.get('project_uuid', '')
        if project_uuid:
            unique_deps[dep_key]['projects'].add(project_uuid)
        
        # Aggregate namespace
        namespace = result.get('namespace', '')
        if namespace:
            unique_deps[dep_key]['namespaces'].add(namespace)
    
    # Convert to list format with aggregated project info
    deduplicated = []
    for dep_key, dep_info in unique_deps.items():
        # Format project UUIDs as semicolon-separated string
        project_uuids = sorted(dep_info['projects'])
        
        deduplicated.append({
            'dependency_name': dep_info['dependency_name'],
            'dependency_version': dep_info['dependency_version'],
            'dependency_scope': dep_info['dependency_scope'],
            'parent_package_version_name': dep_info['parent_package_version_name'],
            'namespaces': ', '.join(sorted(dep_info['namespaces'])),
            'project_count': len(dep_info['projects']),
            'project_uuids': '; '.join(project_uuids) if project_uuids else ''
        })
    
    return deduplicated

def save_results_json(results, filename):
    """Save results to JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to JSON: {filename}")
    except Exception as e:
        print(f"Error saving JSON file: {e}")

def save_results_csv(results, filename):
    """Save results to CSV file."""
    if not results:
        print("No results to save to CSV")
        return
    
    try:
        with open(filename, 'w', newline='') as f:
            # Get all unique keys from all results
            fieldnames = set()
            for result in results:
                fieldnames.update(result.keys())
            fieldnames = sorted(list(fieldnames))
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow(result)
        
        print(f"Results saved to CSV: {filename}")
    except Exception as e:
        print(f"Error saving CSV file: {e}")

def display_results(results):
    """Display results on terminal."""
    print(f"\n{'='*60}")
    print(f"EXPORT RESULTS")
    print(f"{'='*60}")
    
    if not results:
        print("No dependencies found.")
        return
    
    # Count unique namespaces
    all_namespaces = set()
    for result in results:
        namespaces_str = result.get('namespaces', '')
        if namespaces_str:
            all_namespaces.update(namespaces_str.split(', '))
    
    print(f"Found {len(results)} unique dependency(ies) across {len(all_namespaces)} namespace(s)")
    print()
    
    # Display sample of results (first 10)
    print("Sample of unique dependencies (showing first 10):")
    for i, result in enumerate(results[:10], 1):
        print(f"\n{i}. {result['dependency_name']}@{result['dependency_version']}")
        print(f"   Namespaces: {result.get('namespaces', 'N/A')}")
        print(f"   Used in {result.get('project_count', 0)} project(s)")
        if result.get('project_uuids'):
            project_uuids_preview = result['project_uuids'].split('; ')[:3]  # Show first 3 project UUIDs
            print(f"   Project UUIDs: {', '.join(project_uuids_preview)}")
            if result.get('project_count', 0) > 3:
                print(f"   ... and {result.get('project_count', 0) - 3} more")
    
    if len(results) > 10:
        print(f"\n... and {len(results) - 10} more unique dependencies")
    print()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Export all dependencies from all projects.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    args = parser.parse_args()
    
    # Get environment values
    env = get_env_values()
    
    # Get API token
    token = get_token(env["api_key"], env["api_secret"])
    if not token:
        print("Failed to get API token.")
        sys.exit(1)
    
    # Export all dependencies
    results = export_all_dependencies(token, env["initial_namespace"])
    
    # Deduplicate dependencies
    print(f"\nRemoving duplicates (based on dependency name and version)...")
    original_count = len(results)
    results = deduplicate_dependencies(results)
    duplicate_count = original_count - len(results)
    print(f"Removed {duplicate_count} duplicate(s). {len(results)} unique dependency(ies) remaining.")
    
    # Display results
    display_results(results)
    
    # Generate output filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"all_dependencies_export_{timestamp}.json"
    csv_filename = f"all_dependencies_export_{timestamp}.csv"
    
    # Save results
    save_results_json(results, json_filename)
    save_results_csv(results, csv_filename)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total dependencies exported: {len(results)}")
    print(f"Results saved to: {json_filename}, {csv_filename}")

if __name__ == "__main__":
    main()
