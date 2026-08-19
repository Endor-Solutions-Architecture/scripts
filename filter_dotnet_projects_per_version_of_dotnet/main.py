import requests
from dotenv import load_dotenv
import os
import argparse
import csv
from datetime import datetime


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

def get_dotnet_projects():
    query_data = {
        "tenant_meta": {
            "namespace": ""
        },
        "meta": {
            "name": "Projects and Latest Scan Metrics"
        },
        "spec": {
            "query_spec": {
                "kind": "Project",
                "list_parameters": {
                    "mask": "uuid,meta.name,meta.version,tenant_meta.namespace",
                    "traverse": True
                },
                "references": [
                    {
                        "connect_from": "uuid",
                        "connect_to": "meta.parent_uuid",
                        "query_spec": {
                            "kind": "ScanResult",
                            "list_parameters": {
                                "filter": "context.type in [CONTEXT_TYPE_MAIN]",
                                "sort": {
                                    "path": "meta.create_time",
                                    "order": "SORT_ENTRY_ORDER_DESC"
                                },
                                "page_size": 1,
                                "mask": "spec.provisioning_result.auto_detect_result.detected_versions,spec.provisioning_result.tool_chains.dotnet_tool_chain",
                                "traverse": True
                            }
                        }
                    }
                ]
            }
        }
    }

    # Define the queries endpoint URL
    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/queries"
    print(f"POST Request to URL: {url}")

    dotnet_projects = []
    next_page_id = None

    try:
        while True:
            if next_page_id:
                query_data["spec"]["query_spec"]["list_parameters"]["page_token"] = next_page_id

            # Make the POST request to the queries endpoint
            response = requests.post(url, headers=HEADERS, json=query_data, timeout=600)

            if response.status_code != 200:
                print(f"Failed to fetch .NET projects. Status Code: {response.status_code}, Response: {response.text}")
                return []

            # Parse the response data
            response_data = response.json()
            projects = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])

            # Process the results
            for project in projects:
                project_uuid = project.get("uuid")
                project_name = project.get("meta", {}).get("name")
                project_version = project.get("meta", {}).get("version")
                tenant_name = project.get("tenant_meta", {}).get("namespace")
                
                # Check if this project has .NET versions detected
                references = project.get("meta", {}).get("references", {})
                dotnet_versions = []
                
                # Get ScanResult references
                scan_result_refs = references.get("ScanResult", {})
                if scan_result_refs:
                    scan_results = scan_result_refs.get("list", {}).get("objects", [])
                    for scan_result in scan_results:
                        provisioning_result = scan_result.get("spec", {}).get("provisioning_result")
                        if provisioning_result:
                            # First check auto_detect_result.detected_versions.dotnet
                            detected_versions = provisioning_result.get("auto_detect_result", {}).get("detected_versions", {})
                            if "dotnet" in detected_versions:
                                dotnet_info = detected_versions["dotnet"]
                                if "values" in dotnet_info:
                                    for version_info in dotnet_info["values"]:
                                        if "version" in version_info:
                                            dotnet_versions.append(version_info["version"])
                            
                            # Only check tool_chains.dotnet_tool_chain if no dotnet versions found in auto-detection
                            if not dotnet_versions:
                                tool_chains = provisioning_result.get("tool_chains", {})
                                if tool_chains and "dotnet_tool_chain" in tool_chains:
                                    dotnet_tool_chain = tool_chains["dotnet_tool_chain"]
                                    if dotnet_tool_chain:
                                        # Get main dotnet version
                                        version_info = dotnet_tool_chain.get("version", {})
                                        if "name" in version_info:
                                            dotnet_versions.append(version_info["name"])
                                        
                                        # Get additional dotnet versions
                                        additional_versions = dotnet_tool_chain.get("additional_dotnet_versions", [])
                                        dotnet_versions.extend(additional_versions)
                            
                            print(f"dotnet_versions: {dotnet_versions}")
                
                if dotnet_versions:
                    # Remove duplicates and sort versions
                    unique_sorted_versions = sorted(list(set(dotnet_versions)))
                    
                    project_info = {
                        "uuid": project_uuid,
                        "name": project_name,
                        "version": project_version,
                        "tenant_name": tenant_name,
                        "dotnet_versions": unique_sorted_versions
                    }
                    dotnet_projects.append(project_info)
                    print(f"Found .NET project: {project_name} ({project_uuid}) with .NET versions: {unique_sorted_versions}")

            # Check for next page
            next_page_id = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("response", {}).get("next_page_token")
            if not next_page_id:
                break
        return dotnet_projects

    except requests.RequestException as e:
        print(f"An error occurred while fetching .NET projects: {e}")
        return []

def create_csv_report(projects, filename=None):
    """Create a CSV report of .NET projects"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dotnet_projects_report_{timestamp}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['project_uuid', 'project_name', 'project_version', 'tenant_name', 'dotnet_versions', 'dotnet_versions_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Write project data
        for project in projects:
            # Join dotnet versions with semicolon for CSV
            versions_str = '; '.join(project['dotnet_versions'])
            
            writer.writerow({
                'project_uuid': project['uuid'],
                'project_name': project['name'],
                'project_version': project['version'],
                'tenant_name': project['tenant_name'],
                'dotnet_versions': versions_str,
                'dotnet_versions_count': len(project['dotnet_versions'])
            })
    
    print(f"CSV report created: {filename}")
    return filename

def main():
    projects = get_dotnet_projects()
    print(f"Found {len(projects)} .NET projects.")
    
    if projects:
        csv_filename = create_csv_report(projects)
        print(f"Report saved to: {csv_filename}")
    else:
        print("No .NET projects found to report.")


if __name__ == "__main__":
    main()