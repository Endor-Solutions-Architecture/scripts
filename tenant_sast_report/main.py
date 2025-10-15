#!/usr/bin/env python3
"""
Script to generate SAST findings report using endorctl.
Takes namespace as required parameter and tags as optional parameter.
Generates a CSV report with project SAST findings summary including language breakdown.
"""

import subprocess
import json
import csv
import sys
import argparse
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict


def run_endorctl_command(command: str, namespace: str) -> Optional[Dict[str, Any]]:
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


def get_projects(namespace: str, project_tags: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all projects, optionally filtered by project tags."""
    print(f"Retrieving projects for namespace: {namespace}")
    
    if project_tags:
        command = f"api list -r Project --filter \"meta.tags matches '{project_tags}'\" --field-mask=\"meta.name,tenant_meta\" --list-all"
        print(f"Filtering projects by tags: {project_tags}")
    else:
        command = f"api list -r Project --field-mask=\"meta.name,tenant_meta\" --list-all"
        print("Retrieving all projects")
    
    response = run_endorctl_command(command, namespace)
    
    if not response:
        print("Error: Failed to retrieve projects.")
        return []
    
    objects = response.get("list", {}).get("objects", [])
    print(f"Retrieved {len(objects)} projects")
    
    return objects


def get_project_findings(namespace: str, project_uuid: str, findings_tags: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get SAST findings for a specific project, optionally filtered by findings tags."""
    if findings_tags:
        command = f"api list -r Finding --filter \"spec.project_uuid=={project_uuid} and spec.finding_categories contains FINDING_CATEGORY_SAST and context.type==CONTEXT_TYPE_MAIN and (meta.description matches '{findings_tags}' or meta.tags matches '{findings_tags}')\" --field-mask=\"spec.finding_metadata.custom.languages,spec.level\" --list-all"
    else:
        command = f"api list -r Finding --filter \"spec.project_uuid=={project_uuid} and spec.finding_categories contains FINDING_CATEGORY_SAST and context.type==CONTEXT_TYPE_MAIN\" --field-mask=\"spec.finding_metadata.custom.languages,spec.level\" --list-all"
    
    response = run_endorctl_command(command, namespace)
    
    if not response:
        return []
    
    return response.get("list", {}).get("objects", [])


def process_project_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process findings to extract counts and language breakdown."""
    total = len(findings)
    critical = 0
    high = 0
    language_counts = defaultdict(int)
    
    for finding in findings:
        # Count severity levels
        level = finding.get("spec", {}).get("level", "")
        if level == "FINDING_LEVEL_CRITICAL":
            critical += 1
        elif level == "FINDING_LEVEL_HIGH":
            high += 1
        
        # Count languages
        languages = finding.get("spec", {}).get("finding_metadata", {}).get("custom", {}).get("languages", [])
        for language in languages:
            language_counts[language] += 1
    
    return {
        "total": total,
        "critical": critical,
        "high": high,
        "language_counts": dict(language_counts)
    }


def generate_report(projects: List[Dict[str, Any]], namespace: str, findings_tags: Optional[str] = None) -> None:
    """Generate the SAST findings report."""
    if not projects:
        print("No projects found to process.")
        return
    
    # Create generated_reports directory if it doesn't exist
    os.makedirs("generated_reports", exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if findings_tags:
        # Sanitize findings_tags for filename (replace spaces and special chars with underscores)
        safe_findings_tags = findings_tags.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")
        output_filename = f"generated_reports/tenant_{namespace}_sast_summary_{safe_findings_tags}_{timestamp}.csv"
    else:
        output_filename = f"generated_reports/tenant_{namespace}_sast_summary_{timestamp}.csv"
    
    # Collect all unique languages across all projects
    all_languages = set()
    project_data = []
    
    print(f"Processing {len(projects)} projects...")
    
    for i, project in enumerate(projects, 1):
        project_uuid = project.get("uuid", "")
        project_name = project.get("meta", {}).get("name", "Unknown")
        tenant_namespace = project.get("tenant_meta", {}).get("namespace", namespace)
        
        print(f"Processing project {i}/{len(projects)}: {project_name}")
        
        # Get findings for this project
        findings = get_project_findings(namespace, project_uuid, findings_tags)
        
        # Process findings
        findings_data = process_project_findings(findings)
        
        # Collect languages for this project
        all_languages.update(findings_data["language_counts"].keys())
        
        # Create project URL
        endor_url = f"https://app.endorlabs.com/t/{tenant_namespace}/projects/{project_uuid}"
        
        project_data.append({
            "uuid": project_uuid,
            "tenant": tenant_namespace,
            "name": project_name,
            "endor_url": endor_url,
            "total": findings_data["total"],
            "critical": findings_data["critical"],
            "high": findings_data["high"],
            "language_counts": findings_data["language_counts"]
        })
    
    # Sort languages alphabetically
    sorted_languages = sorted(all_languages)
    
    # Sort projects by total findings count (descending)
    project_data.sort(key=lambda x: x["total"], reverse=True)
    
    # Write CSV report
    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        # Define fieldnames
        fieldnames = ["uuid", "tenant", "name", "endor_url", "total", "critical", "high"] + sorted_languages
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for project in project_data:
            row = {
                "uuid": project["uuid"],
                "tenant": project["tenant"],
                "name": project["name"],
                "endor_url": project["endor_url"],
                "total": project["total"],
                "critical": project["critical"],
                "high": project["high"]
            }
            
            # Add language counts
            for language in sorted_languages:
                row[language] = project["language_counts"].get(language, 0)
            
            writer.writerow(row)
    
    print(f"\nReport generated successfully: {output_filename}")
    print(f"Total projects processed: {len(projects)}")
    print(f"Languages found: {', '.join(sorted_languages) if sorted_languages else 'None'}")


def main():
    """Main function to orchestrate the SAST report generation."""
    parser = argparse.ArgumentParser(description="Generate SAST findings report")
    parser.add_argument("-n", "--namespace", required=True, help="Namespace to process")
    parser.add_argument("--project-tags", help="Optional tags filter for projects (e.g., 'prod-sast')")
    parser.add_argument("--findings-tags", help="Optional tags filter for findings (e.g., 'security')")
    
    args = parser.parse_args()
    
    namespace = args.namespace
    project_tags = args.project_tags
    findings_tags = args.findings_tags
    
    print(f"Starting SAST report generation")
    print(f"Namespace: {namespace}")
    if project_tags:
        print(f"Project tags filter: {project_tags}")
    if findings_tags:
        print(f"Findings tags filter: {findings_tags}")
    print("-" * 50)
    
    # Check if endorctl is available
    try:
        subprocess.run(["endorctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: endorctl is not available. Please ensure it's installed and in your PATH.")
        sys.exit(1)
    
    # Get projects
    projects = get_projects(namespace, project_tags)
    
    # Generate report
    generate_report(projects, namespace, findings_tags)
    
    print("\nSAST report generation completed successfully!")


if __name__ == "__main__":
    main()
