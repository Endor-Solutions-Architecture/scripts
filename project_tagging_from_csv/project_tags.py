import requests
import os
import csv  # Add this import to handle CSV parsing
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

API_URL = 'https://api.endorlabs.com/v1'
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
GITORG = os.getenv("GITORG")

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



def get_project_details(project_name):
    """Fetch project UUID and existing tags using the project name."""
    token = get_token()
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/projects"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd"
    }
    # Correct filter for spec.git.full_name
    params = {'list_parameters.filter': f'spec.git.full_name=="{project_name}"'}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        response_data = response.json()
        projects = response_data.get('list', {}).get('objects', [])
        if not projects:
            print(f"No project found with full_name: {project_name}, skipping...\n")
            return None, []
        
        project = projects[0]  # Assuming the project name is unique
        project_uuid = project.get('uuid')
        existing_tags = project.get('meta', {}).get('tags', [])
        return project_uuid, existing_tags
    else:
        raise Exception(f"Failed to fetch project details: {response.status_code}, {response.text} \n")


def add_tags_to_project(project_name, tags):
    """Add tags to a project."""
    project_name = GITORG + "/" + project_name
    project_uuid, existing_tags = get_project_details(project_name)
    new_tags = list(set(existing_tags + tags))  # Merge existing and new tags, avoiding duplicates
    
    if project_uuid:
        token = get_token()
        """Add tags to a project."""
        url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/projects"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd"
        }
        payload = {
            "request": {
                "update_mask": "meta.tags"
            },
            "object": {
                "uuid": project_uuid,
                "meta": {
                    "tags": new_tags
                }
            }
        }

        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Tags added successfully to project {project_uuid}: {new_tags} \n")
        else:
            print(f"Failed to add tags to project {project_uuid}: {response.status_code}, {response.text} \n")

if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        print("Usage: python project_tags.py <csv_file_name>")
        sys.exit(1)
    cvs_name = sys.argv[1]

    # Updated CSV parsing logic
    with open(cvs_name, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) < 2:
                continue
            project_name = row[0].strip()
            tags = [tag.strip() for tag in row[1].strip('"').split(',') if tag.strip()]
            tags = [tag.replace(' ', '_') if len(tag.split()) == 2 else tag for tag in tags]
            print(f"Project Name: {project_name}, Tags: {tags}")

            add_tags_to_project(project_name, tags)