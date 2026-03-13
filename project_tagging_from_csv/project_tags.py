import requests
import os
import csv
import sys
import argparse
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_URL = "https://api.endorlabs.com/v1"


def get_token():
    """Resolve a bearer token using the following precedence:
    1. ENDOR_TOKEN environment variable (e.g. from endorctl auth --print-access-token)
    2. API_KEY / API_SECRET credentials (exchanged for a token via the API)
    """
    token = os.getenv("ENDOR_TOKEN")
    if token:
        return token

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    if not api_key or not api_secret:
        print(
            "Error: No authentication method available.\n"
            "Either set ENDOR_TOKEN (recommended):\n"
            '  export ENDOR_TOKEN="$(endorctl auth --print-access-token)"\n'
            "Or provide API_KEY and API_SECRET in your .env file."
        )
        sys.exit(1)

    url = f"{API_URL}/auth/api-key"
    payload = {"key": api_key, "secret": api_secret}
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("token")
    else:
        raise Exception(
            f"Failed to get token: {response.status_code}, {response.text}"
        )


def get_project_details(namespace, project_name):
    """Fetch project UUID and existing tags using the project name."""
    token = get_token()
    url = f"{API_URL}/namespaces/{namespace}/projects"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
    }
    params = {"list_parameters.filter": f'spec.git.full_name=="{project_name}"'}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        response_data = response.json()
        projects = response_data.get("list", {}).get("objects", [])
        if not projects:
            print(f"No project found with full_name: {project_name}, skipping...\n")
            return None, []

        project = projects[0]
        project_uuid = project.get("uuid")
        existing_tags = project.get("meta", {}).get("tags", [])
        return project_uuid, existing_tags
    else:
        raise Exception(
            f"Failed to fetch project details: {response.status_code}, {response.text}\n"
        )


def add_tags_to_project(namespace, gitorg, project_name, tags):
    """Add tags to a project."""
    full_name = gitorg + "/" + project_name
    project_uuid, existing_tags = get_project_details(namespace, full_name)
    new_tags = list(set(existing_tags + tags))

    if project_uuid:
        token = get_token()
        url = f"{API_URL}/namespaces/{namespace}/projects"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
        }
        payload = {
            "request": {"update_mask": "meta.tags"},
            "object": {
                "uuid": project_uuid,
                "meta": {"tags": new_tags},
            },
        }

        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(
                f"Tags added successfully to project {project_uuid}: {new_tags}\n"
            )
        else:
            print(
                f"Failed to add tags to project {project_uuid}: {response.status_code}, {response.text}\n"
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bulk-tag Endor Labs projects from a CSV file."
    )
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument(
        "--namespace",
        default=os.getenv("ENDOR_NAMESPACE"),
        help="Endor Labs namespace (overrides ENDOR_NAMESPACE env var)",
    )
    parser.add_argument(
        "--gitorg",
        default=os.getenv("GITORG"),
        help="Git organization name (overrides GITORG env var)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.namespace:
        print("Error: --namespace is required (or set ENDOR_NAMESPACE env var).")
        sys.exit(1)
    if not args.gitorg:
        print("Error: --gitorg is required (or set GITORG env var).")
        sys.exit(1)

    with open(args.csv_file, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) < 2:
                continue
            project_name = row[0].strip()
            tags = [tag.strip() for tag in row[1].strip('"').split(",") if tag.strip()]
            tags = [
                tag.replace(" ", "_") if len(tag.split()) == 2 else tag for tag in tags
            ]
            print(f"Project Name: {project_name}, Tags: {tags}")
            add_tags_to_project(args.namespace, args.gitorg, project_name, tags)
