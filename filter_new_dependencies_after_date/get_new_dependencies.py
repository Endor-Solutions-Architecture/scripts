#!/usr/bin/env python3
"""
Script to get a list of dependencies that are new to a project after a specific date.
Queries DependencyMetadata for the project and filters by creation date.
"""

import argparse
import csv
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

def parse_date(date_string):
    """
    Parse date string in various formats and return datetime object.
    Supports formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SSZ
    """
    date_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S"
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_string}. Supported formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SSZ")

def format_date_for_api(date_obj):
    """
    Format datetime object for API filter.
    Returns date() function format suitable for API date comparison.
    Converts to UTC and formats as date(YYYY-MM-DD) as expected by the API.
    """
    # Convert to UTC if timezone-aware
    if date_obj.tzinfo is not None:
        date_obj = date_obj.astimezone(timezone.utc)
    
    # Format as date(YYYY-MM-DD) - API expects this format
    date_only = date_obj.strftime("%Y-%m-%d")
    return f"date({date_only})"

def get_new_dependencies(namespace, token, project_uuid, cutoff_date, branch=None):
    """
    Query DependencyMetadata for a project and get all dependencies created on or after the cutoff date.
    
    Args:
        namespace: The namespace for the project
        token: API authentication token
        project_uuid: UUID of the project
        cutoff_date: datetime object representing the cutoff date
        branch: Optional branch name. If provided, filters by context.id==branch, otherwise uses context.type==CONTEXT_TYPE_MAIN
    
    Returns:
        List of dictionaries containing dependency information
    """
    url = f"{API_URL}/namespaces/{namespace}/dependency-metadata"
    headers = {
        "Authorization": f"Bearer {token}",
        "Request-Timeout": "600"
    }
    
    # Format date for API filter
    date_str = format_date_for_api(cutoff_date)
    print(f"DEBUG: Date string passed to filter: \"{date_str}\"")
    
    # Build context filter based on whether branch is provided
    if branch:
        context_part = f"context.id=={branch}"
        context_desc = f"branch context: {branch}"
    else:
        context_part = "context.type==CONTEXT_TYPE_MAIN"
        context_desc = "main context"
    
    # Filter by project UUID, context, and creation date in the API call
    # Use date() function format as expected by the API
    context_filter = f"spec.importer_data.project_uuid=={project_uuid} and meta.create_time>={date_str} and {context_part}"
    print(f"DEBUG: Full filter string: {context_filter}")
    print(f"Using {context_desc}")
    
    params = {
        "list_parameters.filter": context_filter,
        "list_parameters.mask": "meta.name,meta.create_time,spec.dependency_data,spec.importer_data"
    }
    
    new_dependencies = []
    next_page_id = None
    page_num = 1
    
    print(f"Querying DependencyMetadata for project {project_uuid}...")
    print(f"Filtering for dependencies created on or after: {cutoff_date.isoformat()}")
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id
        
        try:
            print(f"Fetching dependencies page {page_num}...")
            response = requests.get(url, headers=headers, params=params, timeout=600)
            response.raise_for_status()
            
            data = response.json()
            objects = data.get('list', {}).get('objects', [])
            print(f"Received {len(objects)} dependencies on page {page_num}")
            
            for obj in objects:
                dep_data = obj.get('spec', {}).get('dependency_data', {})
                package_name = dep_data.get('package_name', '')
                resolved_version = dep_data.get('resolved_version', '')
                created_str = obj.get('meta', {}).get('create_time', '')
                
                # Extract just the package name from format like "npm://merge"
                if package_name and '://' in package_name:
                    package_name = package_name.split('://')[-1]
                
                dependency_info = {
                    'package_name': package_name,
                    'resolved_version': resolved_version,
                    'created_date': created_str,
                    'uuid': obj.get('uuid'),
                    'name': obj.get('meta', {}).get('name', '')
                }
                
                new_dependencies.append(dependency_info)
                print(f"Found new dependency: {package_name}@{resolved_version} (created: {created_str})")
            
            next_page_id = data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
            
            page_num += 1
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to get dependencies: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return []
    
    print(f"Total new dependencies found: {len(new_dependencies)}")
    return new_dependencies

def generate_output_filenames(project_uuid, date_str, branch=None):
    """
    Generate output filenames based on project UUID, date, and optionally branch.
    
    Args:
        project_uuid: The project UUID
        date_str: The date string (sanitized for filename)
        branch: Optional branch name to include in filename
    
    Returns:
        Tuple of (json_filename, csv_filename)
    """
    # Sanitize date string for filename (remove special characters)
    safe_date = date_str.replace('-', '').replace('T', '_').replace(':', '').split('+')[0].split('Z')[0]
    # Sanitize branch name for filename (remove special characters)
    if branch:
        safe_branch = branch.replace('/', '_').replace('\\', '_').replace(' ', '_')
        base_name = f"{project_uuid}_new_dependencies_{safe_date}_{safe_branch}"
    else:
        base_name = f"{project_uuid}_new_dependencies_{safe_date}"
    return f"{base_name}.json", f"{base_name}.csv"

def write_csv_file(filename, dependencies):
    """Write dependencies to a CSV file."""
    if not dependencies:
        # Create empty CSV with headers
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['package_name', 'resolved_version', 'created_date', 'uuid', 'name'])
        return
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['package_name', 'resolved_version', 'created_date', 'uuid', 'name'])
        writer.writeheader()
        writer.writerows(dependencies)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Get a list of dependencies that are new to a project after a specific date.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python get_new_dependencies.py --project_uuid <uuid> --date 2024-01-01
  python get_new_dependencies.py --project_uuid <uuid> --date 2024-01-01T00:00:00Z
  python get_new_dependencies.py --project_uuid <uuid> --date 2024-01-01 --branch feature-branch

Output files will be created automatically:
  - {project_uuid}_new_dependencies_{date}.json (or with _branch suffix if --branch is provided)
  - {project_uuid}_new_dependencies_{date}.csv (or with _branch suffix if --branch is provided)
        """
    )
    parser.add_argument('--project_uuid', type=str, required=True, 
                       help='The UUID of the project')
    parser.add_argument('--date', type=str, required=True,
                       help='Cutoff date (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ). Dependencies created on or after this date will be included.')
    parser.add_argument('--branch', type=str, default=None,
                       help='Branch name. If provided, filters by context.id==branch. Otherwise uses main context (context.type==CONTEXT_TYPE_MAIN).')
    
    args = parser.parse_args()
    
    # Parse the date
    try:
        cutoff_date = parse_date(args.date)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
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
    
    # Get new dependencies
    new_dependencies = get_new_dependencies(namespace, token, args.project_uuid, cutoff_date, args.branch)
    
    # Generate output filenames
    json_filename, csv_filename = generate_output_filenames(args.project_uuid, args.date, args.branch)
    
    # Write JSON file
    with open(json_filename, 'w') as f:
        json.dump(new_dependencies, f, indent=2)
    print(f"\nJSON file saved to: {json_filename}")
    
    # Write CSV file
    write_csv_file(csv_filename, new_dependencies)
    print(f"CSV file saved to: {csv_filename}")
    
    print(f"\nTotal new dependencies: {len(new_dependencies)}")

if __name__ == "__main__":
    main()

