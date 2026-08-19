import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_URL = 'https://api.endorlabs.com/v1'
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")

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

def add_tags_to_packages(package_uuid, tags):
    """Add tags to a packages."""
    token = get_token()
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/package-versions"
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
            "uuid": package_uuid,
            "meta": {
                "tags": tags
            }
        }
    }

    response = requests.patch(url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"Tags added successfully to package {package_uuid}: {tags}")
    else:
        print(f"Failed to add tags to package {package_uuid}: {response.status_code}, {response.text}")

if __name__ == "__main__":
    package_uuid = input("Enter the Package UUID: ")
    tags_input = input("Enter tags to add (comma-separated): ")
    tags = [tag.strip() for tag in tags_input.split(",")]

    add_tags_to_packages(package_uuid, tags)