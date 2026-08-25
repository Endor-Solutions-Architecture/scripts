import requests
import os
from dotenv import load_dotenv
import sys
import argparse
import re

# Load environment variables
load_dotenv()

API_URL = 'https://api.endorlabs.com/v1'
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")

def validate_tag(tag, tag_name):
    """Validate tag format: 63 characters or less, letters, numbers, and (=@_.-) only."""
    if not tag:
        raise ValueError(f"{tag_name} cannot be empty")
    
    if len(tag) > 63:
        raise ValueError(f"{tag_name} must be 63 characters or less (current: {len(tag)} characters)")
    
    # Check for valid characters: letters (A-Z), numbers (0-9), and (=@_.-)
    valid_pattern = r'^[A-Za-z0-9=@_.-]+$'
    if not re.match(valid_pattern, tag):
        raise ValueError(f"{tag_name} may contain only letters (A-Z), numbers (0-9), and the following characters (=@_.-)")
    
    return True

def get_token():
    """Fetch API token using API key and secret."""
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    
    url = f"{API_URL}/auth/api-key"
    payload = {
        "key": api_key,
        "secret": api_secret
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get('token')
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

def get_project_namespace(project_uuid):
    """Fetch project namespace using the project UUID."""
    token = get_token()
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/projects"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd"
    }
    
    # Use filter to find the project by UUID and traverse through namespaces
    params = {
        'list_parameters.filter': f'uuid=="{project_uuid}"',
        'list_parameters.traverse': 'true'  # Traverse through child namespaces
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        response_data = response.json()
        projects = response_data.get('list', {}).get('objects', [])
        
        if not projects:
            raise Exception(f"No project found with UUID: {project_uuid}")
        
        project = projects[0]  # Get the first (and should be only) project
        project_namespace = project.get('tenant_meta', {}).get('namespace')
        print(f"Project namespace: {project_namespace}")
        return project_namespace
    else:
        raise Exception(f"Failed to fetch project details: {response.status_code}, {response.text}")

def get_findings_with_tag(project_uuid, tag, branch=None):
    """Fetch all findings in a project that have the specified tag."""
    project_namespace = get_project_namespace(project_uuid)
    token = get_token()
    url = f"{API_URL}/namespaces/{project_namespace}/findings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd"
    }
    
    # Build filter based on context type
    if branch:
        # Use branch context if specified
        context_filter = f"context.id=={branch} and spec.project_uuid=={project_uuid} and meta.tags CONTAINS \"{tag}\""
        print(f"Using branch context: {branch}")
    else:
        # Default to main context
        context_filter = f"context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=={project_uuid} and meta.tags CONTAINS \"{tag}\""
        print("Using main context")
    
    # Filter findings by project and tag
    params = {
        'list_parameters.filter': context_filter,
        'list_parameters.traverse': 'true'
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        response_data = response.json()
        findings = response_data.get('list', {}).get('objects', [])
        print(f"Found {len(findings)} findings with tag '{tag}'")
        return findings, project_namespace
    else:
        raise Exception(f"Failed to fetch findings: {response.status_code}, {response.text}")

def update_finding_tags(project_uuid, old_tag, new_tag, branch=None):
    """Remove old tag and add new tag to all findings in the project that have the old tag."""
    try:
        findings, project_namespace = get_findings_with_tag(project_uuid, old_tag, branch)
        
        if not findings:
            print(f"No findings found with tag '{old_tag}' in project {project_uuid}")
            return
        
        token = get_token()
        url = f"{API_URL}/namespaces/{project_namespace}/findings"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd"
        }
        
        updated_count = 0
        for finding in findings:
            finding_uuid = finding.get('uuid')
            existing_tags = finding.get('meta', {}).get('tags', [])
            
            # Remove old tag if it exists
            if old_tag in existing_tags:
                existing_tags.remove(old_tag)
                print(f"   Removed tag '{old_tag}' from finding {finding_uuid}")
            
            # Add new tag if it doesn't already exist
            if new_tag not in existing_tags:
                existing_tags.append(new_tag)
                print(f"   Added tag '{new_tag}' to finding {finding_uuid}")
            
            payload = {
                "request": {
                    "update_mask": "meta.tags"
                },
                "object": {
                    "uuid": finding_uuid,
                    "meta": {
                        "tags": existing_tags
                    }
                }
            }

            response = requests.patch(url, json=payload, headers=headers)
            if response.status_code == 200:
                updated_count += 1
                print(f"✅ Successfully updated finding {finding_uuid}")
            else:
                print(f"❌ Failed to update finding {finding_uuid}: {response.status_code}, {response.text}")
        
        print(f"\n✅ Updated {updated_count} out of {len(findings)} findings")
        
    except Exception as e:
        print(f"❌ Error updating findings in project {project_uuid}: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove a tag from findings in a project and replace it with a new tag",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --old-tag "dev-repo" --new-tag "prod-repo" --project-uuid "abc123-def456-ghi789"
  python main.py --old-tag "old-tag" --new-tag "new-tag" --project-uuid "uuid1"
  python main.py --old-tag "dev-repo" --new-tag "prod-repo" --project-uuid "abc123-def456-ghi789" --branch "feature-branch"
        """
    )
    
    parser.add_argument(
        "--old-tag",
        required=True,
        help="Tag to remove from findings"
    )
    
    parser.add_argument(
        "--new-tag", 
        required=True,
        help="Tag to add to findings"
    )
    
    parser.add_argument(
        "--project-uuid",
        required=True,
        help="Project UUID containing the findings to process"
    )
    
    parser.add_argument(
        "--branch",
        required=False,
        help="Branch context to analyze (defaults to main context)"
    )
    
    args = parser.parse_args()
    
    old_tag = args.old_tag
    new_tag = args.new_tag
    project_uuid = args.project_uuid
    branch = args.branch
    
    # Validate tag formats
    try:
        validate_tag(old_tag, "Old tag")
        validate_tag(new_tag, "New tag")
    except ValueError as e:
        print(f"❌ Tag validation error: {e}")
        sys.exit(1)
    
    print(f"Processing findings in project UUID: {project_uuid}")
    print(f"Removing tag '{old_tag}' and adding tag '{new_tag}' to findings...\n")
    
    update_finding_tags(project_uuid, old_tag, new_tag, branch)
    
    print("✅ Findings processed!")