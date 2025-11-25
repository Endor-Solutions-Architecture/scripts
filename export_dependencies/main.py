import requests
import os
import csv  # Add this import to handle CSV parsing
from dotenv import load_dotenv
import sys
import argparse
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables
load_dotenv()

API_URL = 'https://api.endorlabs.com/v1'
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
SESSION: Optional[requests.Session] = None

def _init_shared_session(max_pool: int = 20) -> None:
    """Initialize a global shared Session with connection pooling and basic retries."""
    global SESSION
    if SESSION is not None:
        return
    sess = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=False  # retry on any method
    )
    adapter = HTTPAdapter(pool_connections=max_pool, pool_maxsize=max_pool, max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    # Keep-Alive is default, but ensure header present
    sess.headers.update({"Connection": "keep-alive"})
    SESSION = sess

def _do_request(method: str, url: str, **kwargs) -> requests.Response:
    """Use the shared session if initialized; otherwise fall back to requests.request."""
    if SESSION is not None:
        return SESSION.request(method, url, **kwargs)
    return requests.request(method, url, **kwargs)

def get_token(api_key: Optional[str] = None, api_secret: Optional[str] = None, token: Optional[str] = None) -> str:
    """Return a Bearer token. If token provided, use it; otherwise exchange api_key/secret for a token."""
    # Direct token path
    if token:
        return token

    # Fallback to env if args not provided
    key = api_key or os.getenv("ENDOR_API_CREDENTIALS_KEY")
    secret = api_secret or os.getenv("ENDOR_API_CREDENTIALS_SECRET")

    if not key or not secret:
        raise Exception("Missing API credentials. Provide --api-key/--api-secret or set ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET, or provide --token/ENDOR_TOKEN.")

    url = f"{API_URL}/auth/api-key"
    payload = {
        "key": key,
        "secret": secret
    }
    headers = {"Content-Type": "application/json"}

    response = _do_request("POST", url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get('token')
    else:
        raise Exception(f"Failed to get token: {response.status_code}, {response.text}")


def _authorized_request(method: str, url: str, headers: Dict[str, str], token_box: List[str], api_key: Optional[str], api_secret: Optional[str], **kwargs) -> requests.Response:
    """
    Make a request with Authorization and retry once on 401/403 by refreshing the token
    if api_key/api_secret are available. token_box is a 1-element list to allow in-place updates.
    """
    merged_headers = dict(headers or {})
    merged_headers["Authorization"] = f"Bearer {token_box[0]}"
    resp = _do_request(method, url, headers=merged_headers, **kwargs)
    if resp.status_code in (401, 403) and api_key and api_secret:
        try:
            token_box[0] = get_token(api_key=api_key, api_secret=api_secret, token=None)
            merged_headers["Authorization"] = f"Bearer {token_box[0]}"
            resp = _do_request(method, url, headers=merged_headers, **kwargs)
        except Exception:
            return resp
    return resp


def get_unique_dependencies(namespace: Optional[str] = None, token: Optional[str] = None, api_key: Optional[str] = None, api_secret: Optional[str] = None, debug: bool = False) -> Dict[str, Any]:
    """
    Download and return all unique dependencies aggregated by meta.name from the dependency-metadata API.
    
    This fetches across both CONTEXT_TYPE_MAIN and CONTEXT_TYPE_SBOM, traverses related objects, and
    follows pagination until all results are retrieved.
    """
    ns = namespace or ENDOR_NAMESPACE
    if not ns:
        raise ValueError("Namespace is required. Set ENDOR_NAMESPACE env var or pass namespace argument.")
    
    bearer_token = get_token(api_key=api_key, api_secret=api_secret, token=token)
    token_box: List[str] = [bearer_token]
    url = f"{API_URL}/namespaces/{ns}/dependency-metadata"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800"
    }
    
    params = {
        # Filter for MAIN and SBOM contexts
        "list_parameters.filter": 'context.type in ["CONTEXT_TYPE_MAIN","CONTEXT_TYPE_SBOM"]',
        "list_parameters.traverse": "true",
        "list_parameters.count": "false",
        # Group by meta.name and both possible package_version_uuid fields and include aggregation UUIDs
        "list_parameters.group.aggregation_paths": "meta.name,spec.dependency_data.package_version_uuid,spec.importer_data.package_version_uuid",
        "list_parameters.group.show_aggregation_uuids": "true",
        # Pagination controls
        "list_parameters.page_size": 500
    }
    
    # Merge groups across pages if pagination is present
    merged_groups: Dict[str, Any] = {}
    page_count = 0
    next_page_token: Optional[str] = None
    
    while True:
        page_count += 1
        if next_page_token:
            params["list_parameters.page_token"] = next_page_token
        elif "list_parameters.page_token" in params:
            # Ensure we don't send a stale token on the first page
            params.pop("list_parameters.page_token")
        
        if debug:
            print(f"[debug] dependency-metadata: fetching page {page_count} ...")
        response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch dependency metadata (page {page_count}): {response.status_code}, {response.text}")
        
        data = response.json()
        groups = data.get("group_response", {}).get("groups", {}) or {}
        # Merge groups by key; later pages overwrite earlier duplicates if any
        merged_groups.update(groups)
        if debug:
            print(f"[debug] dependency-metadata: page {page_count} ok; page groups={len(groups)}, merged unique groups={len(merged_groups)}")
        
        # Handle pagination token in either list.response or group_response.response (depending on API)
        next_page_token = (
            data.get("list", {}).get("response", {}).get("next_page_token")
            or data.get("group_response", {}).get("response", {}).get("next_page_token")
        )
        if debug:
            if next_page_token:
                print(f"[debug] dependency-metadata: next page token present, continuing ...")
            else:
                print(f"[debug] dependency-metadata: no next page, aggregation complete")
        if not next_page_token:
            break
    
    return {"group_response": {"groups": merged_groups}}

def extract_dependency_counts_from_groups(groups: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert group_response.groups into a list of dicts aggregated by meta.name:
      - name (meta.name)
      - package_version_uuid: representative uuid (highest associated count)
      - importer_package_version_uuid: representative importer uuid (highest associated count)
      - count: SUM of aggregation_count.count across all groups for that name
    Each key is a JSON-encoded array containing entries like:
      {"key":"meta.name","value":"pypi://urllib3@1.26.20"}
      {"key":"spec.dependency_data.package_version_uuid","value":"66d0988469c594feb187c89a"}
      {"key":"spec.importer_data.package_version_uuid","value":"..."}
    """
    parsed_rows: List[Dict[str, Any]] = []
    for key_str, value in groups.items():
        name = ""
        dep_pkg_uuid = ""
        importer_pkg_uuid = ""
        try:
            parsed_key = json.loads(key_str)
            if isinstance(parsed_key, list) and parsed_key:
                for item in parsed_key:
                    k = item.get("key")
                    v = item.get("value", "")
                    if k == "meta.name":
                        name = v or name
                    elif k == "spec.dependency_data.package_version_uuid":
                        dep_pkg_uuid = v or dep_pkg_uuid
                    elif k == "spec.importer_data.package_version_uuid":
                        importer_pkg_uuid = v or importer_pkg_uuid
        except Exception:
            name = name or ""
        try:
            count = int(value.get("aggregation_count", {}).get("count", 0))
        except Exception:
            count = 0
        if name:
            parsed_rows.append({
                "name": name,
                "package_version_uuid": dep_pkg_uuid,
                "importer_package_version_uuid": importer_pkg_uuid,
                "count": count
            })
    # Aggregate by name: sum counts and choose representative uuids with highest tallies
    aggregated: Dict[str, Dict[str, Any]] = {}
    for row in parsed_rows:
        key = row["name"]
        if key not in aggregated:
            aggregated[key] = {
                "name": key,
                "count": 0,
                "package_version_uuid": "",
                "importer_package_version_uuid": "",
                "_pkg_counts": {},
                "_imp_counts": {}
            }
        agg = aggregated[key]
        agg["count"] += row["count"]
        if row["package_version_uuid"]:
            agg["_pkg_counts"][row["package_version_uuid"]] = agg["_pkg_counts"].get(row["package_version_uuid"], 0) + row["count"]
        if row["importer_package_version_uuid"]:
            agg["_imp_counts"][row["importer_package_version_uuid"]] = agg["_imp_counts"].get(row["importer_package_version_uuid"], 0) + row["count"]
    final: List[Dict[str, Any]] = []
    for _, agg in aggregated.items():
        if agg["_pkg_counts"]:
            agg["package_version_uuid"] = max(agg["_pkg_counts"].items(), key=lambda kv: kv[1])[0]
        if agg["_imp_counts"]:
            agg["importer_package_version_uuid"] = max(agg["_imp_counts"].items(), key=lambda kv: kv[1])[0]
        agg.pop("_pkg_counts", None)
        agg.pop("_imp_counts", None)
        final.append(agg)
    return final

def get_dependencies_details(namespace: Optional[str] = None, token: Optional[str] = None, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute a paginated DependencyMetadata query with references and return the combined results.
    Posts to /v1/namespaces/{namespace}/queries with the provided query spec, traversing all pages.
    """
    ns = namespace or ENDOR_NAMESPACE
    if not ns:
        raise ValueError("Namespace is required. Set ENDOR_NAMESPACE env var or pass namespace argument.")
    
    bearer_token = get_token(api_key=api_key, api_secret=api_secret, token=token)
    token_box: List[str] = [bearer_token]
    url = f"{API_URL}/namespaces/{ns}/queries"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800"
    }
    base_payload: Dict[str, Any] = {
        "tenant_meta": {
            "namespace": ns
        },
        "meta": {
            "name": "QueryDependencies"
        },
        "spec": {
            "query_spec": {
                "kind": "DependencyMetadata",
                "list_parameters": {
                    "page_size": 500,
                    "filter": "context.type in [CONTEXT_TYPE_MAIN,CONTEXT_TYPE_SBOM]",
                    "traverse": True,
                    "mask": "context,meta,spec.dependency_data.direct,spec.dependency_data.namespace,spec.dependency_data.package_version_uuid,spec.dependency_data.reachable,spec.importer_data.project_uuid,spec.importer_data.package_version_name,spec.importer_data.package_version_uuid,spec.importer_data.package_version_ref,tenant_meta,uuid"
                },
                "references": [
                    {
                        "connect_from": "spec.importer_data.project_uuid",
                        "connect_to": "uuid",
                        "query_spec": {
                            "kind": "Project",
                            "list_parameters": {
                                "traverse": True,
                                "mask": "meta.name,spec.platform_source,tenant_meta.namespace,uuid",
                                "page_size": 1
                            },
                            "return_as": "ImportingProject"
                        }
                    },
                    {
                        "connect_from": "context.id",
                        "connect_to": "spec.identifier",
                        "query_spec": {
                            "kind": "ImportedSBOM",
                            "list_parameters": {
                                "traverse": True,
                                "filter": "context.type == CONTEXT_TYPE_SBOM",
                                "mask": "context,meta.name,spec.main_component_purl,tenant_meta,uuid"
                            },
                            "return_as": "ImportingSBOM"
                        }
                    },
                    {
                        "connect_from": "uuid",
                        "connect_to": "spec.target_uuid",
                        "query_spec": {
                            "kind": "Finding",
                            "list_parameters": {
                                "count": True,
                                "filter": "spec.finding_categories contains [\"FINDING_CATEGORY_MALWARE\"] and spec.level in [\"FINDING_LEVEL_CRITICAL\", \"FINDING_LEVEL_HIGH\"]"
                            },
                            "return_as": "MalwareCount"
                        }
                    }
                ]
            }
        }
    }
    combined_objects: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None
    page_count = 0
    while True:
        page_count += 1
        # Create fresh payload per page and set/remove page_token as needed
        payload = json.loads(json.dumps(base_payload))  # deep copy
        lp = payload["spec"]["query_spec"]["list_parameters"]
        if next_page_token:
            lp["page_token"] = next_page_token
        elif "page_token" in lp:
            del lp["page_token"]
        
        response = _authorized_request("POST", url, headers, token_box, api_key, api_secret, json=payload)
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to execute dependencies details query (page {page_count}): {response.status_code}, {response.text}")
        data = response.json()
        # Some queries return results under spec.query_response.list.objects
        objs = (
            data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])
            or data.get("list", {}).get("objects", [])
            or []
        )
        combined_objects.extend(objs)
        next_page_token = data.get("list", {}).get("response", {}).get("next_page_token")
        if not next_page_token:
            break
    return {"list": {"objects": combined_objects}}

def get_dependency_details(package_version_uuid: str, namespace: Optional[str] = None, token: Optional[str] = None, api_key: Optional[str] = None, api_secret: Optional[str] = None, debug: bool = False) -> Dict[str, Any]:
    """
    For a given package_version_uuid, execute the Metric query:
      - filter on meta.parent_uuid (the package_version_uuid)
      - meta.name in ['model_scorecard','pkg_version_info_for_license','package_version_scorecard']
    Posts to /v1/namespaces/{namespace}/queries and keeps tenant_meta.namespace as 'oss'.
    Paginates through all pages and returns combined results.
    """
    ns = namespace or ENDOR_NAMESPACE
    if not ns:
        raise ValueError("Namespace is required. Set ENDOR_NAMESPACE env var or pass namespace argument.")
    if not package_version_uuid:
        # No UUID available; return empty result instead of raising
        return {"list": {"objects": []}}
    
    bearer_token = get_token(api_key=api_key, api_secret=api_secret, token=token)
    token_box: List[str] = [bearer_token]
    # Metrics live under OSS namespace; keep tenant_meta.namespace='oss' and post to OSS endpoint path
    url_ns = "oss"
    url = f"{API_URL}/namespaces/{url_ns}/queries"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800"
    }
    base_payload: Dict[str, Any] = {
        "meta": {
            "name": "QueryDependencyMetrics(namespace: oss)"
        },
        "spec": {
            "query_spec": {
                "kind": "Metric",
                "list_parameters": {
                    "filter": f"meta.parent_uuid in ['{package_version_uuid}'] and meta.name in ['model_scorecard','pkg_version_info_for_license','package_version_scorecard']",
                    "page_size": 500,
                    "mask": "uuid,meta.name,meta.parent_uuid,spec.analytic,spec.metric_values"
                }
            }
        },
        "tenant_meta": {
            "namespace": "oss"
        }
    }
    combined_objects: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None
    page_count = 0
    while True:
        page_count += 1
        payload = json.loads(json.dumps(base_payload))  # deep copy
        lp = payload["spec"]["query_spec"]["list_parameters"]
        if next_page_token:
            lp["page_token"] = next_page_token
        elif "page_token" in lp:
            del lp["page_token"]
        response = _authorized_request("POST", url, headers, token_box, api_key, api_secret, json=payload)
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to execute dependency metrics query (page {page_count}): {response.status_code}, {response.text}")
        data = response.json()
        objs = (
            data.get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])
            or data.get("object", {}).get("spec", {}).get("query_response", {}).get("list", {}).get("objects", [])
            or data.get("list", {}).get("objects", [])
            or []
        )
        if debug:
            print(f"metrics query objects: {len(objs)} (page {page_count})")
        # If no objects on first page, optionally print a brief debug hint
        if debug and page_count == 1 and not objs:
            print(f"debug: no metrics found for package_version_uuid={package_version_uuid}")
        combined_objects.extend(objs)
        next_page_token = (
            data.get("spec", {}).get("query_response", {}).get("response", {}).get("next_page_token")
            or data.get("object", {}).get("spec", {}).get("query_response", {}).get("response", {}).get("next_page_token")
            or data.get("list", {}).get("response", {}).get("next_page_token")
        )
        if not next_page_token:
            break
    return {"list": {"objects": combined_objects}}
 
def extract_metrics_from_dependency_details(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    From a list of Metric objects, extract:
      - spec.metric_values.scorecard.overall_score
      - spec.metric_values.scorecard.category_scores[0..3].{category,score}
      - spec.metric_values.licenseInfoType.license_info.all_licenses[].name (concatenated with ':')
    Returns a dict with keys:
      overall_score, cat0_category, cat0_score, cat1_category, cat1_score, cat2_category, cat2_score, cat3_category, cat3_score, licenses
    """
    result = {
        "overall_score": "",
        "cat0_category": "", "cat0_score": "",
        "cat1_category": "", "cat1_score": "",
        "cat2_category": "", "cat2_score": "",
        "cat3_category": "", "cat3_score": "",
        "licenses": "",
        "category_scores": {},  # map of category name -> score
    }
    license_names: List[str] = []
    # Try to preserve first non-empty values for score fields
    def set_if_empty(key: str, value: Any):
        if value is None:
            return
        if result.get(key, "") in ("", None):
            result[key] = value
    def extract_scorecard_from_container(container: Dict[str, Any]) -> None:
        if not isinstance(container, dict):
            return
        scorecard = container.get("scorecard")
        if not isinstance(scorecard, dict):
            return
        # Support nested "score_card" structure as in sample
        scorecard_payload = scorecard.get("score_card", scorecard)
        set_if_empty("overall_score", scorecard_payload.get("overall_score"))
        categories = scorecard_payload.get("category_scores", []) or []
        for idx in range(4):
            if idx < len(categories) and isinstance(categories[idx], dict):
                cat_obj = categories[idx]
                # category name can be under 'category' or 'name' depending on metric
                cat_name = cat_obj.get("category", cat_obj.get("name"))
                set_if_empty(f"cat{idx}_category", cat_name)
                set_if_empty(f"cat{idx}_score", cat_obj.get("score"))
                # Also populate normalized category -> score map
                if isinstance(cat_name, str) and cat_name and cat_name not in result["category_scores"]:
                    result["category_scores"][cat_name] = cat_obj.get("score")
    for obj in objects:
        spec_obj = obj.get("spec", {}) or {}
        metric_values = spec_obj.get("metric_values", {}) or {}
        analytic = spec_obj.get("analytic", {}) or {}
        # Scorecard metrics can appear either under metric_values.scorecard or analytic.scorecard
        extract_scorecard_from_container(metric_values)
        extract_scorecard_from_container(analytic)
        # License info metrics
        lic_info = metric_values.get("licenseInfoType", {}).get("license_info", {})
        all_licenses = lic_info.get("all_licenses", []) or []
        for lic in all_licenses:
            name = (lic or {}).get("name")
            if name:
                license_names.append(str(name))
    if license_names:
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for n in license_names:
            if n not in seen:
                seen.add(n)
                deduped.append(n)
        result["licenses"] = ":".join(deduped)
    return result


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Export unique dependencies grouped by meta.name")
    parser.add_argument("--namespace", "-n", default=os.getenv("ENDOR_NAMESPACE"), help="Namespace (or set ENDOR_NAMESPACE)")
    parser.add_argument("--api-key", default=os.getenv("ENDOR_API_CREDENTIALS_KEY"), help="API key (or set ENDOR_API_CREDENTIALS_KEY)")
    parser.add_argument("--api-secret", default=os.getenv("ENDOR_API_CREDENTIALS_SECRET"), help="API secret (or set ENDOR_API_CREDENTIALS_SECRET)")
    parser.add_argument("--token", default=os.getenv("ENDOR_TOKEN"), help="Bearer token (or set ENDOR_TOKEN)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--workers", type=int, default=20, help="Number of parallel workers for API calls")
    args = parser.parse_args()

    # Validate namespace
    if not args.namespace:
        print("Error: --namespace or ENDOR_NAMESPACE is required.")
        sys.exit(1)
    # Initialize shared HTTP session with connection pooling sized to workers
    _init_shared_session(max_pool=args.workers)

    # If token not provided, ensure both api-key and api-secret exist
    if not args.token and (not args.api_key or not args.api_secret):
        print("Error: Provide --token/ENDOR_TOKEN or both --api-key/ENDOR_API_CREDENTIALS_KEY and --api-secret/ENDOR_API_CREDENTIALS_SECRET.")
        sys.exit(1)

    try:
        print(f"Aggregating unique dependencies.  This make take a few minutes ...")
        result = get_unique_dependencies(namespace=args.namespace, token=args.token, api_key=args.api_key, api_secret=args.api_secret, debug=args.debug)
        groups = result.get("group_response", {}).get("groups", {}) or {}
        if args.debug:
            print(f"Number of unique dependencies found before de-duplication: {len(groups)}")
        # Build CSV of "dependency_name,count"
        rows = extract_dependency_counts_from_groups(groups)
        # Sort by count descending
        rows.sort(key=lambda r: r["count"], reverse=True)
        # Debug: show effect of deduplication by meta.name
        print(f"Number of unique dependencies after de-duplication: {len(rows)} (removed {len(groups) - len(rows)} duplicates)")

        # Prepare CSV output
        os.makedirs("generated_reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ns_safe = (args.namespace or "namespace").replace("/", "_")
        output_path = f"generated_reports/unique_dependencies_{ns_safe}_{timestamp}.csv"
        # Write header once
        with open(output_path, "w", newline="", encoding="utf-8") as f_header:
            writer = csv.writer(f_header)
            writer.writerow([
                "name",
                "package_version_uuid",
                "count",
                "overall_score",
                "SCORE_CATEGORY_POPULARITY",
                "SCORE_CATEGORY_CODE_QUALITY",
                "SCORE_CATEGORY_SECURITY",
                "SCORE_CATEGORY_ACTIVITY",
                "licenses"
            ])

        # Lock for safe serialized writes
        write_lock = threading.Lock()
        total_metric_records = 0
        total_metric_records_lock = threading.Lock()

        def process_and_write(row: Dict[str, Any]) -> int:
            primary_uuid = row.get("package_version_uuid") or ""
            fallback_uuid = row.get("importer_package_version_uuid") or ""
            objects: List[Dict[str, Any]] = []
            try:
                if primary_uuid:
                    metrics_resp = get_dependency_details(
                        package_version_uuid=primary_uuid,
                        namespace=args.namespace,
                        token=args.token,
                        api_key=args.api_key,
                        api_secret=args.api_secret,
                        debug=False
                    )
                    objects = metrics_resp.get("list", {}).get("objects", []) or []
                if not objects and fallback_uuid and fallback_uuid != primary_uuid:
                    metrics_resp = get_dependency_details(
                        package_version_uuid=fallback_uuid,
                        namespace=args.namespace,
                        token=args.token,
                        api_key=args.api_key,
                        api_secret=args.api_secret,
                        debug=False
                    )
                    objects = metrics_resp.get("list", {}).get("objects", []) or []
                metrics = extract_metrics_from_dependency_details(objects)
                cat_scores = metrics.get("category_scores", {}) or {}
                with write_lock:
                    # Append row safely
                    with open(output_path, "a", newline="", encoding="utf-8") as f_out:
                        writer = csv.writer(f_out)
                        writer.writerow([
                            row["name"],
                            row["package_version_uuid"],
                            row["count"],
                            metrics.get("overall_score", ""),
                            cat_scores.get("SCORE_CATEGORY_POPULARITY", ""),
                            cat_scores.get("SCORE_CATEGORY_CODE_QUALITY", ""),
                            cat_scores.get("SCORE_CATEGORY_SECURITY", ""),
                            cat_scores.get("SCORE_CATEGORY_ACTIVITY", ""),
                            metrics.get("licenses", "")
                        ])
                return len(objects)
            except Exception as ex:
                if args.debug:
                    print(f"\nerror processing {row.get('name')}: {ex}")
                return 0

        # Run in parallel
        print(f"Fetching dependency metrics in parallel with {args.workers} workers ...")
        futures = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            for row in rows:
                futures.append(executor.submit(process_and_write, row))
            completed = 0
            total_futures = len(futures)
            for future in as_completed(futures):
                try:
                    count = future.result()
                    with total_metric_records_lock:
                        total_metric_records += count
                except Exception as e2:
                    if args.debug:
                        print(f"\nworker exception: {e2}")
                completed += 1
                if completed % 25 == 0 or completed == total_futures:
                    print(f"\rcompleted {completed}/{total_futures}", end="", flush=True)
        print()  # newline after progress
        print(f"Total dependency metric records: {total_metric_records}")
        print(output_path)
    except Exception as e:
        print(f"Error fetching unique dependencies: {e}")
