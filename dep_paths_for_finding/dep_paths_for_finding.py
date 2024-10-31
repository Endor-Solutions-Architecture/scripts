import json
import sys
import os
import logging
import requests
from pprint import pprint

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


def get_package_version_dep_graph(auth_token, namespace, package_version_uuid):
    package_version = endor_api_get(auth_token, namespace, f"package-versions/{package_version_uuid}")
    return package_version['spec']['resolved_dependencies']['dependency_graph']


def get_all_dep_paths_for_dep(dep_graph, dep, current_path=None, all_paths=None):
    if current_path is None:
        current_path = []
    if all_paths is None:
        all_paths = set()

    # Add the current node to the path
    current_path.append(dep)

    # Check if the node is in the dependency dictionary
    if dep in dep_graph:
        # If there are no parents (base case), add the path to all_paths
        if not any(dep in deps for deps in dep_graph.values()):
            all_paths.add(tuple(current_path))
        else:
            # Iterate through all items in the dependency dictionary
            for parent, dependencies in dep_graph.items():
                if dep in dependencies:
                    # Recursive call to find parents
                    get_all_dep_paths_for_dep(dep_graph, parent, current_path[:], all_paths)

    return all_paths


if __name__ == "__main__":
    auth_token = endor_api_get_auth_token(ENDOR_API_CREDENTIALS_KEY, ENDOR_API_CREDENTIALS_SECRET)

    finding = get_finding(auth_token, namespace, finding_uuid)
    logger.debug(f"{finding=}")

    target_dep_package_name = finding['spec']['target_dependency_package_name']
    logger.debug(f"{target_dep_package_name=}")
    
    package_version_uuid = finding['meta']['parent_uuid']
    logger.debug(f"{package_version_uuid=}")

    package_version_dep_graph = get_package_version_dep_graph(auth_token, namespace, package_version_uuid)

    #print(json.dumps(package_version_dep_graph, indent=4))

    dep_paths = get_all_dep_paths_for_dep(package_version_dep_graph, target_dep_package_name)

    pprint(dep_paths)



    
