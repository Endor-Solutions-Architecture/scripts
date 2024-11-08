import json
import sys
import os
import logging
import requests

namespace = sys.argv[1]
finding_uuid = sys.argv[2]

logger = logging.getLogger(__name__)
FORMAT = "[%(filename)s:%(lineno)4s - %(funcName)s ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.WARN)

ENDOR_API_CREDENTIALS_KEY = os.getenv("ENDOR_API_CREDENTIALS_KEY")
ENDOR_API_CREDENTIALS_SECRET = os.getenv("ENDOR_API_CREDENTIALS_SECRET")

def endor_api_get_auth_token(api_key: str, api_secret: str):
    url = "https://api.endorlabs.com/v1/auth/api-key"
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


def endor_api_get(auth_token, namespace, uri, params = {}) -> json:
    url=f"https://api.endorlabs.com/v1/namespaces/{namespace}/{uri}"
    logger.debug(f"{url=}")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Request-Timeout": "20"
    }

    response = requests.get(
        url=url,
        params=params,
        headers=headers
    )

    return response.json()


def get_finding(auth_token, namespace, finding_uuid):
    return endor_api_get(auth_token, namespace, f"findings/{finding_uuid}")


def get_package_version(auth_token, namespace, package_version_uuid):
    package_version = endor_api_get(auth_token, namespace, f"package-versions/{package_version_uuid}")
    return package_version

def add_public_to_path(path, package_version):
    path_list = []
    deps_list = package_version['spec']['resolved_dependencies']['dependencies']

    for dep in path:
        dep_match = [x for x in deps_list if x['name'] == dep]
        logger.debug(f"{dep_match=}")
        if not dep_match:
            dep_match = [{"public": False}]
        path_list.append(
            {
                "dependency_name": dep,
                "public": dep_match[0]['public']
            }
        )
    return path_list

def get_all_dep_paths_for_dep(package_version, dep, finding_uuid, current_path=None, all_paths=None):
    dep_graph = package_version['spec']['resolved_dependencies']['dependency_graph']
    if current_path is None:
        current_path = []
    if all_paths is None:
        all_paths = {}
        all_paths[finding_uuid] = []

    # Add the current node to the path
    current_path.append(dep)

    # Check if the node is in the dependency dictionary
    if dep in dep_graph:
        # If there are no parents (base case), add the path to all_paths
        if not any(dep in deps for deps in dep_graph.values()): # or not any(dep in deps for deps in deps_list if deps['public'] is False):
            all_paths[finding_uuid].append(add_public_to_path(current_path, package_version))

        else:
            # Iterate through all items in the dependency dictionary
            for parent, dependencies in dep_graph.items():
                if dep in dependencies:
                    # Recursive call to find parents
                    get_all_dep_paths_for_dep(package_version, parent, finding_uuid, current_path[:], all_paths)

    return all_paths


if __name__ == "__main__":
    auth_token=os.getenv("ENDOR_TOKEN")
    if not auth_token:
        auth_token = endor_api_get_auth_token(ENDOR_API_CREDENTIALS_KEY, ENDOR_API_CREDENTIALS_SECRET)

    finding = get_finding(auth_token, namespace, finding_uuid)
    logger.debug(f"{finding=}")

    target_dep_package_name = finding['spec']['target_dependency_package_name']
    logger.debug(f"{target_dep_package_name=}")
    
    package_version_uuid = finding['meta']['parent_uuid']
    logger.debug(f"{package_version_uuid=}")

    package_version = get_package_version(auth_token, namespace, package_version_uuid)

    #print(json.dumps(package_version_dep_graph, indent=4))

    dep_paths = get_all_dep_paths_for_dep(package_version, target_dep_package_name, finding_uuid)

    print(json.dumps(dep_paths, indent=4))



    
