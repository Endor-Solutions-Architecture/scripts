#!/usr/bin/env python3
"""
Script to export all findings and scan results for all projects across all namespaces in a tenant.

For each tenant:
  For each namespace:
    For each project:
      Export all main findings to file
      Export all main scan results to file

Features:
- Graceful retries with exponential backoff
- Idempotent: can rerun without reprocessing already completed projects
- Tracks progress with state files
- Handles long runtime gracefully
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os
import json
import argparse
import time
import sys
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


# Load environment variables
load_dotenv()

# Configuration
API_URL = 'https://api.endorlabs.com/v1'
DEFAULT_TIMEOUT = 600
SESSION: Optional[requests.Session] = None
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1  # Base delay in seconds for exponential backoff
OUTPUT_DIR = "exports"
STATE_DIR = ".state"

# Thread-safe lock for state file operations
state_lock = Lock()
manifest_lock = Lock()


def get_endor_token() -> str:
    """Get Endor token either directly or by authenticating with API credentials."""
    # Try to get token directly first
    token = os.getenv('ENDOR_TOKEN')
    if token:
        return token

    # If no token, try to get API credentials
    key = os.getenv('ENDOR_API_CREDENTIALS_KEY')
    secret = os.getenv('ENDOR_API_CREDENTIALS_SECRET')
    
    if not key or not secret:
        print("Error: Either ENDOR_TOKEN or both ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET must be set")
        sys.exit(1)

    # Get token using API credentials
    try:
        response = requests.post(
            "https://api.endorlabs.com/v1/auth/api-key",
            json={"key": key, "secret": secret}
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

def get_session() -> requests.Session:
    """Create or return a pooled HTTP session with sane retries for connect/read errors."""
    global SESSION
    if SESSION is not None:
        return SESSION

    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=16, pool_maxsize=32)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    SESSION = session
    return session

def get_headers(token: str) -> Dict[str, str]:
    """Get request headers with authentication."""
    return {
        "User-Agent": "curl/7.68.0",
        "Accept": "*/*",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Request-Timeout": str(DEFAULT_TIMEOUT)
    }


def make_request_with_retry(
    method: str,
    url: str,
    headers: Dict[str, str],
    max_retries: int = MAX_RETRIES,
    timeout_seconds: Optional[int] = None,
    **kwargs
) -> Optional[requests.Response]:
    """
    Make HTTP request with exponential backoff retry logic.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        headers: Request headers
        max_retries: Maximum number of retry attempts
        **kwargs: Additional arguments to pass to requests.request
    
    Returns:
        Response object or None if all retries failed
    """
    session = get_session()
    for attempt in range(max_retries):
        try:
            response = session.request(
                method,
                url,
                headers=headers,
                timeout=timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT,
                **kwargs,
            )
            
            # Retry on server errors (5xx) and rate limiting (429)
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_BASE * (2 ** attempt) + (time.time() % 1)
                    print(f"  Retry {attempt + 1}/{max_retries} after {delay:.2f}s (status {response.status_code})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  Max retries reached for {url}")
                    return None
            else:
                return response
                
        except (requests.Timeout, requests.ConnectionError, requests.ReadTimeout) as e:
            if attempt < max_retries - 1:
                delay = RETRY_DELAY_BASE * (2 ** attempt) + (time.time() % 1)
                print(f"  Retry {attempt + 1}/{max_retries} after {delay:.2f}s (error: {type(e).__name__})")
                time.sleep(delay)
                continue
            else:
                print(f"  Max retries reached for {url}: {e}")
                return None
    
    return None


def paginated_get(
    token: str,
    url: str,
    base_params: Dict[str, Any],
    error_message: Optional[str] = None,
    stop_on_error: bool = False,
    timeout_seconds: Optional[int] = None,
    adaptive_page_size: bool = False,
    min_page_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Make paginated GET requests and collect all objects.
    
    Handles pagination using page_id, automatically fetching all pages.
    
    Args:
        token: Authentication token
        url: Base URL to request
        base_params: Base query parameters (page_id will be added automatically)
        error_message: Optional error message prefix for logging
        stop_on_error: If True, stop on first error; if False, return partial results
    
    Returns:
        List of all objects from all pages
    """
    headers = get_headers(token)
    all_objects = []
    next_page_id = None
    params = base_params.copy()
    # Track current page size for adaptive mode
    current_page_size_key = 'list_parameters.page_size'
    original_page_size = params.get(current_page_size_key)
    if adaptive_page_size and original_page_size is None:
        original_page_size = 500
        params[current_page_size_key] = original_page_size
    
    while True:
        if next_page_id:
            params['list_parameters.page_id'] = next_page_id
        else:
            # Remove page_id from params if we're on first page
            params.pop('list_parameters.page_id', None)
        
        response = make_request_with_retry(
            "GET",
            url,
            headers,
            timeout_seconds=timeout_seconds,
            params=params,
        )
        
        if not response or response.status_code != 200:
            status_msg = f"Status Code: {response.status_code if response else 'None'}"
            if error_message:
                error_msg = f"{error_message} {status_msg}"
            else:
                error_msg = f"Failed to fetch data. {status_msg}"
            print(f"    {error_msg}")

            # Adaptive page size on timeout/5xx if enabled
            if adaptive_page_size and params.get(current_page_size_key, 0) > min_page_size:
                new_size = max(min_page_size, int(params.get(current_page_size_key, original_page_size) / 2))
                if new_size < params.get(current_page_size_key, original_page_size):
                    print(f"    Reducing page_size to {new_size} and retrying page...")
                    params[current_page_size_key] = new_size
                    # brief backoff before retrying the same page
                    time.sleep(1.0)
                    continue

            if stop_on_error:
                break
            # Return partial results if not stopping on error
            break
        
        try:
            response_data = response.json()
            objects = response_data.get('list', {}).get('objects', [])
            all_objects.extend(objects)
            
            next_page_id = response_data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
        except (KeyError, json.JSONDecodeError) as e:
            print(f"    Error parsing response: {e}")
            break
    
    return all_objects


def get_all_namespaces(token: str, primary_namespace: str) -> List[str]:
    """
    Get all namespaces in the tenant.
    
    Uses the namespaces REST endpoint with traverse to get all namespaces across the tenant.
    """
    print("Discovering all namespaces in tenant...")
    headers = get_headers(token)
    
    # Use the namespaces endpoint with traverse to get all namespaces
    url = f"{API_URL}/namespaces"
    params = {
        'list_parameters.mask': 'uuid,meta.name',
        'list_parameters.traverse': True
    }
    
    namespaces = set()
    next_page_id = None
    
    try:
        while True:
            if next_page_id:
                params['list_parameters.page_id'] = next_page_id
            
            response = make_request_with_retry("GET", url, headers, params=params)
            
            if not response or response.status_code != 200:
                print(f"Warning: Failed to fetch namespaces. Status Code: {response.status_code if response else 'None'}")
                # Fallback to using just the primary namespace
                if not namespaces:
                    print(f"  Falling back to primary namespace: {primary_namespace}")
                    return [primary_namespace]
                break
            
            response_data = response.json()
            namespace_objects = response_data.get('list', {}).get('objects', [])
            
            # Extract namespace names from the response
            # Namespace name is typically in meta.name
            for ns_obj in namespace_objects:
                namespace_name = ns_obj.get('meta', {}).get('name')
                if namespace_name:
                    namespaces.add(namespace_name)
            
            next_page_id = response_data.get('list', {}).get('response', {}).get('next_page_id')
            if not next_page_id:
                break
        
        namespace_list = sorted(list(namespaces))
        # If we didn't find namespaces via the endpoint, fall back to projects method
        if not namespace_list:
            print("  Namespaces endpoint didn't return namespaces, extracting from projects...")
            return _get_namespaces_from_projects(token, primary_namespace)
        
        print(f"Found {len(namespace_list)} namespace(s): {', '.join(namespace_list)}")
        return namespace_list if namespace_list else [primary_namespace]
        
    except Exception as e:
        print(f"Error discovering namespaces: {e}")
        print(f"  Falling back to extracting namespaces from projects...")
        return _get_namespaces_from_projects(token, primary_namespace)


def _get_namespaces_from_projects(token: str, primary_namespace: str) -> List[str]:
    """
    Fallback method: Get namespaces by traversing projects and extracting unique namespace values.
    """
    url = f"{API_URL}/namespaces/{primary_namespace}/projects"
    params = {
        'list_parameters.mask': 'uuid,tenant_meta.namespace',
        'list_parameters.traverse': True
    }
    
    projects = paginated_get(token, url, params)
    
    namespaces = set()
    for project in projects:
        namespace = project.get('tenant_meta', {}).get('namespace')
        if namespace:
            namespaces.add(namespace)
    
    namespace_list = sorted(list(namespaces)) if namespaces else [primary_namespace]
    print(f"Found {len(namespace_list)} namespace(s) from projects: {', '.join(namespace_list)}")
    return namespace_list


def get_all_projects(token: str, namespace: str) -> List[Dict[str, Any]]:
    """
    Get all projects in a namespace.
    
    Args:
        token: Authentication token
        namespace: Namespace to query
    
    Returns:
        List of project dictionaries with at least 'uuid' key
    """
    print(f"  Fetching projects in namespace '{namespace}'...")
    
    url = f"{API_URL}/namespaces/{namespace}/projects"
    params = {
        'list_parameters.mask': 'uuid,meta.name',
        'list_parameters.traverse': True
    }
    
    projects = paginated_get(
        token, url, params,
        error_message="Error: Failed to get projects.",
        stop_on_error=True
    )
    
    projects_list = []
    for project in projects:
        projects_list.append({
            'uuid': project.get('uuid'),
            'name': project.get('meta', {}).get('name', 'Unknown')
        })
    
    print(f"    Found {len(projects_list)} project(s)")
    return projects_list


def query_findings_for_project(token: str, namespace: str, project_uuid: str) -> List[Dict[str, Any]]:
    """
    Query all main findings for a project.
    
    Uses the findings REST endpoint with filter for context.type==CONTEXT_TYPE_MAIN and spec.project_uuid.
    
    Args:
        token: Authentication token
        namespace: Namespace
        project_uuid: Project UUID
    
    Returns:
        List of finding objects
    """
    url = f"{API_URL}/namespaces/{namespace}/findings"
    
    filter_str = f"context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=={project_uuid}"
    
    params = {
        "list_parameters.filter": filter_str,
        # Start smaller to avoid timeouts; adaptive will raise/lower as needed
        "list_parameters.page_size": 100,
        "list_parameters.traverse": "true",
        # If supported by the API, hint a longer server-side timeout
        "list_parameters.timeout": "240s",
        # Reduce payload size to return faster
        "list_parameters.mask": (
            "uuid,meta.create_time,context.type,context.id,"
            "spec.project_uuid,spec.summary,spec.target_dependency_name,"
            "spec.target_dependency_version"
        ),
    }
    
    return paginated_get(
        token,
        url,
        params,
        error_message="Warning: Failed to fetch findings.",
        stop_on_error=False,
        timeout_seconds=240,
        adaptive_page_size=True,
        min_page_size=50,
    )


def query_scan_results_for_project(token: str, namespace: str, project_uuid: str) -> List[Dict[str, Any]]:
    """
    Query all main scan results for a project.
    
    Uses the scan-results REST endpoint with filter for context.type==CONTEXT_TYPE_MAIN and meta.parent_uuid.
    
    Args:
        token: Authentication token
        namespace: Namespace
        project_uuid: Project UUID
    
    Returns:
        List of scan result objects
    """
    url = f"{API_URL}/namespaces/{namespace}/scan-results"
    
    filter_str = f"context.type==CONTEXT_TYPE_MAIN and meta.parent_uuid=={project_uuid}"
    
    params = {
        "list_parameters.filter": filter_str,
        "list_parameters.page_size": 200,
        "list_parameters.traverse": "true",
        "list_parameters.timeout": "180s",
        "list_parameters.mask": (
            "uuid,meta.parent_uuid,context.type,spec.start_time,spec.end_time,"
            "spec.status,spec.exit_code"
        ),
    }
    
    return paginated_get(
        token,
        url,
        params,
        error_message="Warning: Failed to fetch scan results.",
        stop_on_error=False,
        timeout_seconds=200,
        adaptive_page_size=True,
        min_page_size=50,
    )


def ensure_directories():
    """Ensure output and state directories exist."""
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(STATE_DIR).mkdir(parents=True, exist_ok=True)


def get_state_file(namespace: str) -> str:
    """Get path to state file for a namespace."""
    return os.path.join(STATE_DIR, f"processed_{namespace.replace('/', '_')}.json")


def load_processed_projects(namespace: str) -> Set[str]:
    """Load set of already processed project UUIDs."""
    state_file = get_state_file(namespace)
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_projects', []))
        except Exception as e:
            print(f"    Warning: Failed to load state file: {e}")
    return set()


def save_processed_project(namespace: str, project_uuid: str):
    """Mark a project as processed in state file (thread-safe)."""
    state_file = get_state_file(namespace)
    
    # Use lock to ensure thread-safe state file updates
    with state_lock:
        # Load existing state
        processed = load_processed_projects(namespace)
        processed.add(project_uuid)
        
        # Save updated state
        try:
            with open(state_file, 'w') as f:
                json.dump({'processed_projects': list(processed)}, f, indent=2)
        except Exception as e:
            print(f"    Warning: Failed to save state file: {e}")


def dump_to_file(data: List[Dict[str, Any]], filepath: str):
    """
    Dump data to JSON file.
    
    Args:
        data: List of objects to write
        filepath: Path to output file
    """
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"      Error writing file {filepath}: {e}")


def export_project_data(token: str, namespace: str, project: Dict[str, Any], force: bool = False) -> Optional[Dict[str, Any]]:
    """
    Export findings and scan results for a single project.
    
    Args:
        token: Authentication token
        namespace: Namespace
        project: Project dictionary with 'uuid' and 'name'
        force: If True, reprocess even if already processed
    """
    project_uuid = project.get('uuid')
    project_name = project.get('name', 'Unknown')
    
    findings_file = os.path.join(OUTPUT_DIR, namespace, f"findings_{project_uuid}.json")
    scan_results_file = os.path.join(OUTPUT_DIR, namespace, f"scanresults_{project_uuid}.json")
    findings_filename = os.path.basename(findings_file)
    scanresults_filename = os.path.basename(scan_results_file)
    
    # Check if already processed (unless force)
    if not force:
        processed = load_processed_projects(namespace)
        if project_uuid in processed:
            print(f"    Skipping project {project_uuid} (already processed)")
            # Try to read counts from existing files
            findings_count = 0
            scanresults_count = 0
            try:
                if os.path.exists(findings_file):
                    with open(findings_file, 'r') as f:
                        findings_data = json.load(f)
                        findings_count = len(findings_data) if isinstance(findings_data, list) else 0
                if os.path.exists(scan_results_file):
                    with open(scan_results_file, 'r') as f:
                        scanresults_data = json.load(f)
                        scanresults_count = len(scanresults_data) if isinstance(scanresults_data, list) else 0
            except Exception:
                pass  # If we can't read, leave counts as 0
            
            return {
                'project_uuid': project_uuid,
                'project_name': project_name,
                'findings_filename': findings_filename,
                'scanresults_filename': scanresults_filename,
                'findings_count': findings_count,
                'scanresults_count': scanresults_count
            }
    
    print(f"    Processing project: {project_name} ({project_uuid})")
    
    # Export findings
    print(f"      Fetching findings...")
    findings = query_findings_for_project(token, namespace, project_uuid)
    findings_count = len(findings)
    print(f"        Found {findings_count} finding(s)")
    
    os.makedirs(os.path.dirname(findings_file), exist_ok=True)
    dump_to_file(findings, findings_file)
    print(f"        Saved to {findings_file}")
    
    # Export scan results
    print(f"      Fetching scan results...")
    scan_results = query_scan_results_for_project(token, namespace, project_uuid)
    scanresults_count = len(scan_results)
    print(f"        Found {scanresults_count} scan result(s)")
    
    os.makedirs(os.path.dirname(scan_results_file), exist_ok=True)
    dump_to_file(scan_results, scan_results_file)
    print(f"        Saved to {scan_results_file}")
    
    # Mark as processed
    save_processed_project(namespace, project_uuid)
    print(f"      Completed project {project_uuid}")
    
    return {
        'project_uuid': project_uuid,
        'project_name': project_name,
        'findings_filename': findings_filename,
        'scanresults_filename': scanresults_filename,
        'findings_count': findings_count,
        'scanresults_count': scanresults_count
    }


def write_manifest_csv(manifest_data: List[Dict[str, Any]], output_file: str):
    """
    Write project export manifest to CSV file.
    
    Args:
        manifest_data: List of dictionaries with project info and file details
        output_file: Path to CSV file to write
    """
    try:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'project_uuid', 
                'project_name', 
                'findings_filename', 
                'scanresults_filename',
                'findings_count',
                'scanresults_count'
            ])
            
            for data in manifest_data:
                writer.writerow([
                    data.get('project_uuid', ''),
                    data.get('project_name', ''),
                    data.get('findings_filename', ''),
                    data.get('scanresults_filename', ''),
                    data.get('findings_count', 0),
                    data.get('scanresults_count', 0)
                ])
        
        print(f"\nManifest CSV written to: {output_file}")
    except Exception as e:
        print(f"Error writing manifest CSV: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export all findings and scan results for all projects across all namespaces in a tenant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all data (resume from previous run if interrupted)
  python main.py
  
  # Force re-export everything (ignore previous progress)
  python main.py --force
  
  # Export only specific namespace
  python main.py --namespace my-namespace
        """
    )
    parser.add_argument(
        '--namespace',
        help='Primary namespace to start from (default: from ENDOR_NAMESPACE env var)',
        default=os.getenv("ENDOR_NAMESPACE")
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-export of all projects (ignore previous progress)'
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=4,
        help='Number of concurrent threads to use for processing projects (default: 4)'
    )
    args = parser.parse_args()
    
    if not args.namespace:
        print("Error: --namespace argument or ENDOR_NAMESPACE environment variable required")
        sys.exit(1)
    
    # Ensure directories exist
    ensure_directories()
    
    # Get authentication token
    print("Authenticating...")
    try:
        token = get_endor_token()
        print("Authentication successful")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Get all namespaces
    namespaces = get_all_namespaces(token, args.namespace)
    
    # Process each namespace
    total_projects = 0
    total_completed = 0
    
    for namespace in namespaces:
        print(f"\n{'='*60}")
        print(f"Processing namespace: {namespace}")
        print(f"{'='*60}")
        
        # Get all projects in namespace
        projects = get_all_projects(token, namespace)
        total_projects += len(projects)
        
        # Manifest data for this namespace
        namespace_manifest_data = []
        
        # Process projects with thread pool
        num_threads = max(1, min(args.threads, len(projects)))  # Ensure reasonable thread count
        print(f"  Using {num_threads} thread(s) to process {len(projects)} project(s)")
        
        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all tasks
                future_to_project = {
                    executor.submit(export_project_data, token, namespace, project, args.force): project
                    for project in projects
                }
                
                # Process completed tasks as they finish
                completed = 0
                for future in as_completed(future_to_project):
                    project = future_to_project[future]
                    completed += 1
                    
                    try:
                        result = future.result()
                        if result:
                            with manifest_lock:
                                namespace_manifest_data.append(result)
                            total_completed += 1
                        print(f"  [{completed}/{len(projects)}] Completed project: {project.get('name', 'Unknown')}")
                    except KeyboardInterrupt:
                        print("\n\nInterrupted by user. Progress has been saved.")
                        print(f"Completed {total_completed}/{total_projects} projects")
                        # Cancel remaining tasks
                        for f in future_to_project:
                            f.cancel()
                        # Write partial manifest before exiting
                        if namespace_manifest_data:
                            manifest_file = os.path.join(OUTPUT_DIR, namespace, "export_manifest.csv")
                            write_manifest_csv(namespace_manifest_data, manifest_file)
                        sys.exit(0)
                    except Exception as e:
                        print(f"  Error processing project {project.get('uuid')}: {e}")
                        print(f"  Continuing with next project...")
            
            # Write manifest CSV for this namespace
            if namespace_manifest_data:
                manifest_file = os.path.join(OUTPUT_DIR, namespace, "export_manifest.csv")
                write_manifest_csv(namespace_manifest_data, manifest_file)
                print(f"  Namespace manifest written to: {manifest_file}")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Progress has been saved.")
            # Write partial manifest for this namespace if we have data
            if namespace_manifest_data:
                manifest_file = os.path.join(OUTPUT_DIR, namespace, "export_manifest.csv")
                write_manifest_csv(namespace_manifest_data, manifest_file)
            print(f"Completed {total_completed}/{total_projects} projects")
            sys.exit(0)
    
    print(f"\n{'='*60}")
    print(f"Export complete!")
    print(f"  Total projects processed: {total_completed}/{total_projects}")
    print(f"  Output directory: {OUTPUT_DIR}/")
    print(f"  State directory: {STATE_DIR}/")
    print(f"  Manifest CSV files: One per namespace in {OUTPUT_DIR}/<namespace>/export_manifest.csv")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

