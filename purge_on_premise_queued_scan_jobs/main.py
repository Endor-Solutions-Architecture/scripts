#!/usr/bin/env python3
"""
Script to purge on-premise queued scan jobs using endorctl.
Takes tenant and persist parameters to control behavior.
"""

import subprocess
import json
import csv
import sys
import argparse
import os
from datetime import datetime
from typing import List, Dict, Any, Optional


def run_endorctl_command(command: str, namespace: str) -> Dict[str, Any]:
    """Executes an endorctl command and returns the parsed JSON response."""
    full_command = f"endorctl -n {namespace} {command}"
    try:
        result = subprocess.run(
            full_command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {full_command}")
        print(f"Error: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw output: {result.stdout}")
        sys.exit(1)


def count_queued_scans(namespace: str) -> int:
    """Count the number of queued on-premise scan requests."""
    print(f"Counting queued on-premise scan requests in namespace: {namespace}")
    
    command = "api list -r ScanRequest --filter 'spec.status==SCAN_REQUEST_STATUS_QUEUED and spec.type==SCAN_REQUEST_TYPE_SCHEDULED and spec.is_on_premise==true' -t 300s --traverse --count"
    
    response = run_endorctl_command(command, namespace)
    
    count = response.get("count_response", {}).get("count", 0)
    print(f"Found {count} queued on-premise scan requests")
    
    return count


def get_queued_scans(namespace: str) -> List[Dict[str, Any]]:
    """Get the list of queued on-premise scan requests with required fields."""
    print(f"Retrieving queued on-premise scan requests from namespace: {namespace}")
    
    command = "api list -r ScanRequest --filter 'spec.status==SCAN_REQUEST_STATUS_QUEUED and spec.type==SCAN_REQUEST_TYPE_SCHEDULED and spec.is_on_premise==true' --field-mask 'uuid,tenant_meta.namespace,spec.project_uuid,spec.installation_uuid' -t 300s --traverse --list-all"
    
    response = run_endorctl_command(command, namespace)
    
    objects = response.get("list", {}).get("objects", [])
    print(f"Retrieved {len(objects)} scan request objects")
    
    return objects


def delete_scan_request(uuid: str, namespace: str) -> bool:
    """Delete a scan request and return success status."""
    command = f"api delete -r ScanRequest --uuid {uuid}"
    
    try:
        result = subprocess.run(
            f"endorctl -n {namespace} {command}",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error deleting scan request {uuid}: {e.stderr}")
        return False


def process_scan_requests(scan_requests: List[Dict[str, Any]], persist: bool, output_filename: str):
    """Process scan requests and write results to CSV."""
    results = []
    
    for scan_request in scan_requests:
        uuid = scan_request.get("uuid", "")
        namespace = scan_request.get("tenant_meta", {}).get("namespace", "")
        project_uuid = scan_request.get("spec", {}).get("project_uuid", "")
        installation_uuid = scan_request.get("spec", {}).get("installation_uuid", "")
        
        # Determine the identifier type for logging
        identifier = project_uuid if project_uuid else installation_uuid
        identifier_type = "project_uuid" if project_uuid else "installation_uuid"
        
        deleted = False
        
        if persist:
            print(f"Deleting Scan Request with Id {uuid} from namespace {namespace}, {identifier_type}: {identifier}")
            deleted = delete_scan_request(uuid, namespace)
            print(f"  Success: {deleted}")
        else:
            print(f"Processing Scan Request with Id {uuid} from namespace {namespace}, {identifier_type}: {identifier} (dry run)")
        
        results.append({
            "scan_request_id": uuid,
            "namespace": namespace,
            "project_uuid": project_uuid,
            "installation_uuid": installation_uuid,
            "deleted": deleted
        })
    
    # Write results to CSV
    with open(output_filename, 'w', newline='') as csvfile:
        fieldnames = ["scan_request_id", "namespace", "project_uuid", "installation_uuid", "deleted"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    print(f"\nResults written to: {output_filename}")
    
    # Summary
    total_processed = len(results)
    total_deleted = sum(1 for r in results if r["deleted"])
    
    print(f"\nSummary:")
    print(f"  Total scan requests processed: {total_processed}")
    if persist:
        print(f"  Total scan requests deleted: {total_deleted}")
        print(f"  Total scan requests failed to delete: {total_processed - total_deleted}")
    else:
        print(f"  Dry run mode - no deletions performed")


def main():
    """Main function to orchestrate the scan request purging process."""
    parser = argparse.ArgumentParser(description="Purge on-premise queued scan jobs")
    parser.add_argument("-n", "--namespace", required=True, help="Tenant namespace to process")
    parser.add_argument("--persist", choices=["true", "false"], required=True, help="Whether to actually delete the scan requests")
    
    args = parser.parse_args()
    
    tenant = args.namespace
    persist = args.persist == "true"
    
    print(f"Starting scan request purge process")
    print(f"Tenant: {tenant}")
    print(f"Persist mode: {persist}")
    print("-" * 50)
    
    # Check if endorctl is available
    try:
        subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.")
        sys.exit(1)
    
    # Count queued scans
    count = count_queued_scans(tenant)
    
    if count == 0:
        print("No queued on-premise scan requests found. Exiting.")
        sys.exit(0)
    
    # Get scan requests
    scan_requests = get_queued_scans(tenant)
    
    if not scan_requests:
        print("No scan request objects retrieved. Exiting.")
        sys.exit(0)
    
    # Create generated_reports directory if it doesn't exist
    os.makedirs("generated_reports", exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"generated_reports/purge_scans_tenant_{tenant}_{timestamp}.csv"
    
    # Process scan requests
    process_scan_requests(scan_requests, persist, output_filename)
    
    print("\nScan request purge process completed successfully!")


if __name__ == "__main__":
    main()
