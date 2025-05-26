#!/usr/bin/env python3

import os
import sys
import requests
from github import Github
from dotenv import load_dotenv
from urllib.parse import quote
from typing import Dict, Set, Tuple

# Load environment variables from .env file
load_dotenv()

def get_github_client(token):
    """Create and return a GitHub client instance"""
    return Github(token)

def get_token():
    API_URL = 'https://api.endorlabs.com/v1'
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    url = f"{API_URL}/auth/api-key"
    payload = {
        "key": api_key,
        "secret": api_secret
    }
    headers = {
        "Content-Type": "application/json",
        "Request-Timeout": "60"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    
    if response.status_code == 200:
        token = response.json().get('token')
        return token
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")

def get_github_repos_with_topics(org_name: str) -> Dict[str, Set[str]]:
    """
    Step 1: Fetch all GitHub repositories with topics
    
    Args:
        org_name (str): Name of the GitHub organization or user
        
    Returns:
        Dict[str, Set[str]]: Dictionary mapping repository URLs to their topics
    """
    try:
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable is not set")
            
        github_client = get_github_client(github_token)
        
        try:
            org = github_client.get_organization(org_name)
            repos = org.get_repos()
        except Exception as e:
            print(f"Failed to get organization, trying as user: {str(e)}")
            user = github_client.get_user(org_name)
            repos = user.get_repos()
        
        # Store repos with their topics
        repos_with_topics = {}
        for repo in repos:
            topics = repo.get_topics()
            if topics:  # Only store repos with topics
                repos_with_topics[repo.html_url] = set(topics)
        
        return repos_with_topics
        
    except Exception as e:
        print(f"Error fetching GitHub repositories: {str(e)}")
        sys.exit(1)

def get_endor_project_info(repo_url: str) -> Tuple[str, Set[str]]:
    """
    Step 2: Get project information from Endor Labs API
    
    Args:
        repo_url (str): GitHub repository URL
        
    Returns:
        Tuple[str, Set[str]]: Tuple containing (project_uuid, existing_tags)
    """
    try:
        endor_token = get_token()
        endor_namespace = os.getenv("ENDOR_NAMESPACE")
        
        base_url = f"https://api.endorlabs.com/v1/namespaces/{endor_namespace}/projects"
        filter_param = f"meta.name=={quote(repo_url)}"
        url = f"{base_url}?list_parameters.filter={filter_param}"
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {endor_token}'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if data and 'list' in data and 'objects' in data['list'] and len(data['list']['objects']) > 0:
            project = data['list']['objects'][0]
            return (
                project.get('uuid'),
                set(project.get('meta', {}).get('tags', []))
            )
        return None, set()
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling Endor Labs API: {str(e)}")
        return None, set()

def update_endor_project_tags(project_uuid: str, tags: Set[str]) -> bool:
    """
    Step 3: Update project tags in Endor Labs
    
    Args:
        project_uuid (str): UUID of the project
        tags (Set[str]): Set of tags to update
        
    Returns:
        bool: True if update was successful
    """
    try:
        endor_token = get_token()
        endor_namespace = os.getenv("ENDOR_NAMESPACE")
        
        url = f"https://api.endorlabs.com/v1/namespaces/{endor_namespace}/projects"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {endor_token}'
        }
        
        # Convert tags to list and sort for consistent output
        tags_list = sorted(list(tags))
        
        payload = {
            "object": {
                "uuid": project_uuid,
                "meta": {
                    "tags": tags_list
                }
            },
            "request": {
                "update_mask": "meta.tags"
            }
        }
        
        # print(f"\nDebug - Update Request:")
        # print(f"URL: {url}")
        # print(f"Headers: {headers}")
        # print(f"Payload: {payload}")
        
        response = requests.patch(url, json=payload, headers=headers)
        
        # print(f"Response Status: {response.status_code}")
        # print(f"Response Headers: {response.headers}")
        # print(f"Response Body: {response.text}")
        
        response.raise_for_status()
        
        # If we get here, the request was successful
        # print(f"Successfully updated tags: {tags_list}")
        return True
        
    except requests.exceptions.RequestException as e:
        # print(f"\nError updating Endor Labs project tags:")
        # print(f"Error Type: {type(e).__name__}")
        # print(f"Error Message: {str(e)}")
        # if hasattr(e, 'response') and e.response is not None:
        #     print(f"Response Status: {e.response.status_code}")
        #     print(f"Response Headers: {e.response.headers}")
        #     print(f"Response Body: {e.response.text}")
        return False

def main():
    try:
        # Get organization name from environment
        org_name = os.getenv('GITHUB_ORG')
        
        # Step 1: Get GitHub repos with topics
        print("\nStep 1: Fetching GitHub repositories with topics...")
        repos_with_topics = get_github_repos_with_topics(org_name)
        print(f"Found {len(repos_with_topics)} repositories with topics")
        
        # Step 2 & 3: Process each repository
        print("\nStep 2 & 3: Processing repositories in Endor Labs...")
        print("-" * 120)
        print(f"{'Repository URL':<40} | {'Existing Tags':<20} | {'New Tags':<20} | {'Combined Tags':<20} | {'Status'}")
        print("-" * 120)
        
        for repo_url, github_topics in repos_with_topics.items():
            # Get Endor project info
            project_uuid, existing_tags = get_endor_project_info(f"{repo_url}.git")
            
            if project_uuid:
                # Calculate new tags (tags that are in github_topics but not in existing_tags)
                new_tags = github_topics - existing_tags
                # Combine existing and new tags
                combined_tags = existing_tags.union(github_topics)
                
                # Update tags
                success = update_endor_project_tags(project_uuid, combined_tags)
                status = "Updated" if success else "Failed"
                
                print(f"{repo_url:<40} | {', '.join(existing_tags):<20} | {', '.join(new_tags):<20} | {', '.join(combined_tags):<20} | {status}")
            else:
                print(f"{repo_url:<40} | {'N/A':<20} | {', '.join(github_topics):<20} | {', '.join(github_topics):<20} | Skipped")
        
        print("-" * 120)
            
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
