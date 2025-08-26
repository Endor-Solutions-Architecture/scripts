#!/usr/bin/env python3
"""
Script to generate action policy notifications report using endorctl.
Takes namespace and policy-uuid parameters to generate a CSV report of notifications.
"""

import subprocess
import json
import csv
import sys
import argparse
import os
import urllib.parse
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
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw output: {result.stdout}")
        return None


def get_policy_details(namespace: str, policy_uuid: str) -> Optional[Dict[str, Any]]:
    """Get policy details and validate it's a notification policy."""
    print(f"Retrieving policy details for UUID: {policy_uuid}")
    
    command = f"api get -r Policy --uuid={policy_uuid} --field-mask='meta.name,spec.policy_type'"
    
    response = run_endorctl_command(command, namespace)
    
    if not response:
        print(f"Error: Policy with UUID {policy_uuid} was not found.")
        return None
    
    policy_name = response.get("meta", {}).get("name", "Unknown")
    policy_type = response.get("spec", {}).get("policy_type", "")
    
    print(f"Found policy: {policy_name}")
    print(f"Policy type: {policy_type}")
    
    if policy_type != "POLICY_TYPE_NOTIFICATION":
        print(f"Error: This is not a notification policy. Policy type is: {policy_type}")
        return None
    
    return {
        "name": policy_name,
        "uuid": policy_uuid,
        "type": policy_type
    }


def get_notifications(namespace: str, policy_uuid: str) -> List[Dict[str, Any]]:
    """Get notifications for a specific policy."""
    print(f"Retrieving notifications for policy: {policy_uuid}")
    
    command = f"api list -r Notification --filter='spec.policy_uuid==\"{policy_uuid}\"' --field-mask='uuid,context.id,spec.state,spec.project_uuid,spec.notification_action_data' --list-all"
    
    response = run_endorctl_command(command, namespace)
    
    if not response:
        print("Error: Failed to retrieve notifications.")
        return []
    
    objects = response.get("list", {}).get("objects", [])
    print(f"Retrieved {len(objects)} notifications")
    
    return objects


def get_project_names(namespace: str, project_uuids: List[str]) -> Dict[str, str]:
    """Get project names for a list of project UUIDs."""
    if not project_uuids:
        return {}
    
    print(f"Retrieving project names for {len(project_uuids)} projects")
    
    # Create filter string for multiple UUIDs
    uuid_list = "', '".join(project_uuids)
    command = f"api list --resource Project --namespace {namespace} --filter \"uuid in ['{uuid_list}']\" --traverse --field-mask=\"uuid,spec.git.full_name\""
    
    response = run_endorctl_command(command, namespace)
    
    if not response:
        print("Error: Failed to retrieve project names.")
        return {}
    
    projects = {}
    objects = response.get("list", {}).get("objects", [])
    
    for project in objects:
        uuid = project.get("uuid", "")
        full_name = project.get("spec", {}).get("git", {}).get("full_name", "Unknown")
        projects[uuid] = full_name
    
    return projects


def extract_jira_data(notification_action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract JIRA-related data from notification_action_data."""
    jira_data = {
        "jira_id": "",
        "was_created": False,
        "was_updated": False,
        "was_resolved": False
    }
    
    if not notification_action_data:
        return jira_data
    
    # Find JIRA action
    for action_id, action_data in notification_action_data.items():
        if action_data.get("notification_target_type") == "ACTION_TYPE_JIRA":
            jira_data["was_created"] = action_data.get("open_action_complete", False)
            jira_data["was_updated"] = action_data.get("update_action_complete", False)
            jira_data["was_resolved"] = action_data.get("resolve_action_complete", False)
            
            # Get JIRA issue key if available
            metadata = action_data.get("metadata", {})
            data = metadata.get("data", {})
            jira_data["jira_id"] = data.get("issue_key", "")
            break
    
    return jira_data


def extract_errors(notification_action_data: Dict[str, Any]) -> str:
    """Extract and aggregate errors from notification_action_data."""
    errors = []
    
    if not notification_action_data:
        return ""
    
    for action_id, action_data in notification_action_data.items():
        error_status = action_data.get("error_status", "")
        notification_target_type = action_data.get("notification_target_type", "")
        
        if error_status:
            errors.append(f"{notification_target_type}_{error_status}")
    
    return "|".join(errors)


def process_notifications(notifications: List[Dict[str, Any]], namespace: str, policy_name: str, policy_uuid: str, policy_name_for_filter: str):
    """Process notifications and generate CSV report."""
    if not notifications:
        print("No notifications found to process.")
        return
    
    # Extract unique project UUIDs
    project_uuids = list(set([
        notification.get("spec", {}).get("project_uuid", "")
        for notification in notifications
        if notification.get("spec", {}).get("project_uuid")
    ]))
    
    # Get project names
    project_names = get_project_names(namespace, project_uuids)
    
    # Create generated_reports directory if it doesn't exist
    os.makedirs("generated_reports", exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_policy_name = policy_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    output_filename = f"generated_reports/policy_{policy_uuid}_{safe_policy_name}_{timestamp}.csv"
    
    # Process notifications and collect data for sorting
    notification_data = []
    
    for notification in notifications:
            uuid = notification.get("uuid", "")
            context = notification.get("context", {})
            spec = notification.get("spec", {})
            notification_action_data = spec.get("notification_action_data", {})
            
            project_uuid = spec.get("project_uuid", "")
            project_name = project_names.get(project_uuid, "Unknown")
            branch = context.get("id", "")
            state = spec.get("state", "")
            
            # Extract JIRA data
            jira_data = extract_jira_data(notification_action_data)
            
            # Extract errors
            errors = extract_errors(notification_action_data)
            
            # Create notification link based on state
            encoded_policy_name = urllib.parse.quote(policy_name_for_filter)
            if state in ["NOTIFICATION_STATE_OPEN", "NOTIFICATION_STATE_OPEN_NOTIFICATION_PENDING"]:
                notification_link = f"https://app.endorlabs.com/t/{namespace}/notifications/open?resourceDetail={{\"notificationUuid\":\"{uuid}\"}}&filter.search={encoded_policy_name}"
            else:
                notification_link = f"https://app.endorlabs.com/t/{namespace}/notifications/resolved?resourceDetail={{\"notificationUuid\":\"{uuid}\"}}&filter.search={encoded_policy_name}"
            
            # Create project URL
            project_url = f"https://app.endorlabs.com/t/{namespace}/projects/{project_uuid}"
            
            notification_data.append({
                "notification_uuid": uuid,
                "notification_link": notification_link,
                "state": state,
                "branch": branch,
                "project_name": project_name,
                "project_url": project_url,
                "jira_id": jira_data["jira_id"],
                "was_created": jira_data["was_created"],
                "was_updated": jira_data["was_updated"],
                "was_resolved": jira_data["was_resolved"],
                "errors": errors
            })
    
    # Sort the data by project_name, state, and branch
    notification_data.sort(key=lambda x: (x["project_name"], x["state"], x["branch"]))
    
    # Write sorted data to CSV
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            "notification_uuid", "notification_link", "state", "branch", "project_name", 
            "project_url", "jira_id", "was_created", "was_updated", "was_resolved", "errors"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in notification_data:
            writer.writerow(row)
    
    print(f"\nReport generated successfully: {output_filename}")
    print(f"Total notifications processed: {len(notifications)}")


def main():
    """Main function to orchestrate the notification report generation."""
    parser = argparse.ArgumentParser(description="Generate action policy notifications report")
    parser.add_argument("-n", "--namespace", required=True, help="Namespace to process")
    parser.add_argument("--policy-uuid", required=True, help="Policy UUID to generate report for")
    
    args = parser.parse_args()
    
    namespace = args.namespace
    policy_uuid = args.policy_uuid
    
    print(f"Starting notification report generation")
    print(f"Namespace: {namespace}")
    print(f"Policy UUID: {policy_uuid}")
    print("-" * 50)
    
    # Check if endorctl is available
    try:
        subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.")
        sys.exit(1)
    
    # Get and validate policy details
    policy_details = get_policy_details(namespace, policy_uuid)
    if not policy_details:
        sys.exit(1)
    
    # Get notifications for the policy
    notifications = get_notifications(namespace, policy_uuid)
    
    # Process notifications and generate report
    process_notifications(notifications, namespace, policy_details["name"], policy_uuid, policy_details["name"])
    
    print("\nNotification report generation completed successfully!")


if __name__ == "__main__":
    main()
