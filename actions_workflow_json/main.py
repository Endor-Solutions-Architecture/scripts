import requests
from dotenv import load_dotenv
import os
import json
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
    "Request-Timeout": "600"
}

def get_github_action_packages_with_projects():
    print("Fetching GitHub Action packages with project data...")
    
    query_data = {
        "tenant_meta": {
            "namespace": ""
        },
        "meta": {
            "name": "GitHub Action Packages with Projects"
        },
        "spec": {
            "query_spec": {
                "kind": "PackageVersion",
                "list_parameters": {
                    "filter": "spec.ecosystem == 'ECOSYSTEM_GITHUB_ACTION' and context.type == 'CONTEXT_TYPE_MAIN'",
                    "mask": "uuid,meta.name,spec.project_uuid,spec.resolved_dependencies.dependencies",
                    "traverse": True
                },
                "references": [
                    {
                        "connect_from": "spec.project_uuid",
                        "connect_to": "uuid",
                        "query_spec": {
                            "kind": "Project",
                            "list_parameters": {
                                "mask": "uuid,meta.name",
                                "traverse": True
                            }
                        }
                    }
                ]
            }
        }
    }

    url = f"{API_URL}/namespaces/{ENDOR_NAMESPACE}/queries"
    print(f"URL: {url}")
    
    packages_list = []
    next_page_id = None

    while True:
        if next_page_id:
            query_data["spec"]["query_spec"]["list_parameters"]["page_token"] = next_page_id

        response = requests.post(url, headers=HEADERS, json=query_data, timeout=600)

        if response.status_code != 200:
            print(f"Failed to get packages, Status Code: {response.status_code}, Response: {response.text}")
            exit()

        response_data = response.json()
        print(f"Response status: {response.status_code}")
        
        # Debug: Print response structure keys
        if "spec" in response_data:
            print("Found 'spec' in response")
            if "query_response" in response_data["spec"]:
                print("Found 'query_response' in spec")
            else:
                print("'query_response' not in spec, available keys:", list(response_data["spec"].keys()))
        else:
            print("'spec' not in response, available keys:", list(response_data.keys()))
        
        packages = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])
        print(f"Found {len(packages)} packages in this batch")
        
        for package in packages:
            if package is None:
                print("Warning: Found None package, skipping")
                continue
                
            # Get package info
            package_uuid = package.get("uuid") if package else ""
            package_name = package.get("meta", {}).get("name", "") if package.get("meta") else ""
            project_uuid = package.get("spec", {}).get("project_uuid", "") if package.get("spec") else ""
            
            print(f"Processing package: {package_name} (UUID: {package_uuid})")
            
            # Get dependencies
            dependencies = []
            if package.get("spec") and package["spec"].get("resolved_dependencies"):
                resolved_deps = package["spec"]["resolved_dependencies"].get("dependencies", [])
                for dep in resolved_deps:
                    if dep:  # Check if dep is not None
                        dependency_info = {
                            "name": dep.get("name", ""),
                            "public": dep.get("public", False),
                            "source_repository_http_clone_url": dep.get("source_repository_http_clone_url", ""),
                            "source_repository_ref": dep.get("source_repository_ref", ""),
                            "platform_source": dep.get("platform_source", ""),
                            "purl": dep.get("purl", "")
                        }
                        dependencies.append(dependency_info)
            
            print(f"  Found {len(dependencies)} dependencies")
            
            # Get referenced project info
            project_data = {}
            # Check if references exist in the response_data at the top level
            if "references" in response_data.get("spec", {}).get("query_response", {}):
                references = response_data["spec"]["query_response"]["references"]
                print(f"  Found references at top level: {len(references)}")
                if references:
                    project_objects = references[0].get("list", {}).get("objects", [])
                    if project_objects:
                        project = project_objects[0]
                        project_data = {
                            "uuid": project.get("uuid", ""),
                            "name": project.get("meta", {}).get("name", "")
                        }
                        print(f"  Found project: {project_data.get('name')} ({project_data.get('uuid')})")
            
            package_info = {
                "package_uuid": package_uuid,
                "package_name": package_name,
                "project_uuid": project_uuid,
                "dependencies": dependencies,
                "project": project_data
            }
            packages_list.append(package_info)

        next_page_id = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("response", {}).get("next_page_token")
        if not next_page_id:
            break

    print(f"Total GitHub Action packages fetched: {len(packages_list)}")
    
    # Group packages by project
    projects_dict = {}
    for package_info in packages_list:
        project_uuid = package_info["project_uuid"]
        project_data = package_info["project"]
        
        if project_uuid not in projects_dict:
            projects_dict[project_uuid] = {
                "uuid": project_uuid,
                "name": project_data.get("name", ""),
                "packages": []
            }
        
        # Add package to project
        package_data = {
            "package_uuid": package_info["package_uuid"],
            "package_name": package_info["package_name"],
            "dependencies": package_info["dependencies"]
        }
        projects_dict[project_uuid]["packages"].append(package_data)
    
    # Convert to list
    projects_list = list(projects_dict.values())
    
    print(f"Total projects with GitHub Action packages: {len(projects_list)}")
    return projects_list

def get_dependency_scores(dependency_names):
    """Get Endor Labs scores for a list of dependency names"""
    if not dependency_names:
        return {}
    
    print(f"Fetching scores for {len(dependency_names)} dependencies...")
    
    # Create filter for all dependency names
    name_filters = " or ".join([f"meta.name == '{name}'" for name in dependency_names])
    
    query_data = {
        "tenant_meta": {
            "namespace": "oss"  # Use oss namespace for package data
        },
        "meta": {
            "name": "PackageVersion Scores Query"
        },
        "spec": {
            "query_spec": {
                "kind": "PackageVersion",
                "list_parameters": {
                    "filter": f"({name_filters})",
                    "mask": "uuid,meta.name",
                    "traverse": True
                },
                "references": [
                    {
                        "connect_from": "uuid",  # PackageVersion UUID
                        "connect_to": "meta.parent_uuid",  # Metric parent_uuid - you can fix this connection
                        "query_spec": {
                            "kind": "Metric",
                            "list_parameters": {
                                "filter": "meta.name == 'package_version_scorecard'",
                                "mask": "uuid,meta.name,meta.parent_uuid,spec.metric_values.scorecard.score_card.category_scores",
                                "traverse": True
                            }
                        }
                    }
                ]
            }
        }
    }

    
    url = f"{API_URL}/namespaces/oss/queries"
    scores_dict = {}
    next_page_id = None
    
    try:
        while True:
            if next_page_id:
                query_data["spec"]["query_spec"]["list_parameters"]["page_token"] = next_page_id

            response = requests.post(url, headers=HEADERS, json=query_data, timeout=600)

            if response.status_code != 200:
                print(f"Failed to get dependency scores, Status Code: {response.status_code}, Response: {response.text}")
                break

            response_data = response.json()
            packages = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])
            
            for package in packages:
                if package is None:
                    continue
                    
                package_name = package.get("meta", {}).get("name", "")
                package_uuid = package.get("uuid", "")
                
                # Get referenced metric scores from package's own references
                scores = {}
                package_references = package.get("meta", {}).get("references", {})
                if "Metric" in package_references:
                    metric_response = package_references["Metric"]
                    metric_objects = metric_response.get("list", {}).get("objects", [])
                    for metric in metric_objects:
                        if metric and metric.get("meta", {}).get("name") == "package_version_scorecard":
                            category_scores = metric.get("spec", {}).get("metric_values", {}).get("scorecard", {}).get("score_card", {}).get("category_scores", [])
                            scores = category_scores
                            break
                
                scores_dict[package_name] = {
                    "uuid": package_uuid,
                    "scores": scores
                }
                
                if scores:
                    print(f"  ✓ Found scores for: {package_name} - {len(scores)} categories")
                else:
                    print(f"  ✗ No scores found for: {package_name}")
            
            next_page_id = response_data.get("spec", {}).get("query_response", {}).get("list", {}).get("response", {}).get("next_page_token")
            if not next_page_id:
                break
                
    except Exception as e:
        print(f"Error fetching dependency scores: {e}")
    
    print(f"Retrieved scores for {len(scores_dict)} dependencies")
    return scores_dict



def save_json_report(data, filename=None):
    """Save the data as a JSON report"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"github_actions_dependencies_scores_report_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=2, ensure_ascii=False)
    
    print(f"JSON report created: {filename}")
    return filename

def main():
    try:
        # Get GitHub Action packages grouped by project
        projects_data = get_github_action_packages_with_projects()
        
        # Collect all unique dependency names for score lookup
        all_dependency_names = set()
        for project in projects_data:
            for package in project["packages"]:
                for dependency in package["dependencies"]:
                    dep_name = dependency.get("name")
                    if dep_name:
                        all_dependency_names.add(dep_name)
        
        print(f"\nFound {len(all_dependency_names)} unique dependencies")
        
        # Get scores for all dependencies
        dependency_scores = get_dependency_scores(list(all_dependency_names))
        
        # Enrich dependency data with scores
        for project in projects_data:
            for package in project["packages"]:
                for dependency in package["dependencies"]:
                    dep_name = dependency.get("name")
                    if dep_name in dependency_scores:
                        dependency["endor_scores"] = dependency_scores[dep_name]["scores"]
                        dependency["oss_uuid"] = dependency_scores[dep_name]["uuid"]
                    else:
                        dependency["endor_scores"] = {}
                        dependency["oss_uuid"] = ""
        
        # Calculate total packages and dependencies across all projects
        total_packages = sum(len(project["packages"]) for project in projects_data)
        total_dependencies = sum(
            len(package["dependencies"]) 
            for project in projects_data 
            for package in project["packages"]
        )
        
        # Create the final report structure
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_projects": len(projects_data),
                "total_github_action_packages": total_packages,
                "total_dependencies": total_dependencies,
                "unique_dependencies": len(all_dependency_names),
                "dependencies_with_scores": len(dependency_scores)
            },
            "projects": projects_data
        }
        
        # Save to JSON file
        json_filename = save_json_report(report)
        
        print(f"\n=== SUMMARY ===")
        print(f"Total projects with GitHub Actions: {len(projects_data)}")
        print(f"Total GitHub Action packages: {total_packages}")
        print(f"Total dependencies: {total_dependencies}")
        print(f"Unique dependencies: {len(all_dependency_names)}")
        print(f"Dependencies with scores: {len(dependency_scores)}")
        print(f"Report saved to: {json_filename}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()