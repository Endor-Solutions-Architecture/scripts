import requests
from dotenv import load_dotenv
import os
import argparse


# Load the environment variables from the .env file
load_dotenv()

# Get the API key and secret from environment variables
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
API_URL = 'https://api.endorlabs.com/v1'

def get_token():
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

API_TOKEN = get_token()
HEADERS = {
    "User-Agent": "curl/7.68.0",
    "Accept": "*/*",
    "Authorization": f"Bearer {API_TOKEN}",
    "Request-Timeout": "600"  # Set the request timeout to 60 seconds
}

def get_test_packages():
    print("Fetching test packages...")
    query_data = {
        "tenant_meta": {
            "namespace": ""
        },
        "meta": {
            "name": "Get all test packages"
        },
        "spec": {
            "query_spec": {
                "kind": "PackageVersion",
                "list_parameters": {
                    "filter": "context.type==CONTEXT_TYPE_MAIN and spec.relative_path matches '(?i).*(tests?|testing|test|testdata).*'",
                    "mask": "uuid,spec.project_uuid,spec.relative_path,tenant_meta",
                    "traverse": True
                }
            }
        }
    }

    # Define the queries endpoint URL
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/queries"
    print(f"POST Request to URL: {url}")
    print(f"Using filter: {query_data['spec']['query_spec']['list_parameters']['filter']}")

    test_packages = []
    next_page_id = None

    try:
        while True:
            if next_page_id:
                query_data["spec"]["query_spec"]["list_parameters"]["page_token"] = next_page_id

            # Make the POST request to the queries endpoint
            response = requests.post(url, headers=HEADERS, json=query_data, timeout=600)

            if response.status_code != 200:
                print(f"Failed to fetch test packages. Status Code: {response.status_code}, Response: {response.text}")
                return []

            # Parse the response data
            response_data = response.json()
            packages = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])

            # Process the results
            for package in packages:
                package_uuid = package.get("uuid")
                tenant_name = package.get("tenant_meta", {}).get("namespace")
                project_uuid = package.get("spec", {}).get("project_uuid")
                relative_path = package.get("spec", {}).get("relative_path")
                test_packages.append(package)
                print(f"Found test package: {package_uuid}, tenant-name: {tenant_name}, project-uuid: {project_uuid}, relative_path: {relative_path}")

            # Check for next page
            next_page_id = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("response", {}).get("next_page_token")
            if not next_page_id:
                break

        return list(test_packages)

    except requests.RequestException as e:
        print(f"An error occurred while fetching test packages: {e}")
        return []


def delete_test_packages(test_packages):
    print("Attempting to delete test packages...")
    for package in test_packages:
        package_uuid = package.get("uuid")
        tenant_name = package.get("tenant_meta", {}).get("namespace")

        if package_uuid and tenant_name:
            url = f"{API_URL}/namespaces/{tenant_name}/package-versions/{package_uuid}"
            try:
                print(f"Deleting test package with UUID: {package_uuid}")
                response = requests.delete(url, headers=HEADERS, timeout=60)
                if response.status_code == 200:
                    print(f"Successfully deleted package with UUID: {package_uuid}")
                else:
                    print(f"Failed to delete package with UUID: {package_uuid}. Status Code: {response.status_code}, Response: {response.text}")
            except requests.RequestException as e:
                print(f"An error occurred while deleting package with UUID: {package_uuid}: {e}")
        else:
            print(f"Skipping package: Missing UUID or tenant name. Package details: {package}")


def main():
    parser = argparse.ArgumentParser(description="Fetch and potentially delete test packages.")
    parser.add_argument('--no-dry-run', action='store_true', help="Fetch and delete all identified test packages.")
    args = parser.parse_args()

    test_packages = get_test_packages()
    print(f"Found {len(test_packages)} test packages.")

    if args.no_dry_run:
        delete_test_packages(test_packages)
    else:
        print("Dry run mode: No packages will be deleted. To delete all identified test packages, run the script with the --no-dry-run flag.")

if __name__ == "__main__":
    main()