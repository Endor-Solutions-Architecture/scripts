import os
import sys
import csv
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

API_URL = "https://api.endorlabs.com/v1"
ENDOR_NAMESPACE = os.getenv("ENDOR_NAMESPACE")
SESSION: Optional[requests.Session] = None

# Secret findings: spec.finding_categories includes FINDING_CATEGORY_SECRETS
SECRETS_FINDINGS_FILTER = (
    "context.type==CONTEXT_TYPE_MAIN and spec.finding_categories contains ['FINDING_CATEGORY_SECRETS']"
)

FINDINGS_MASK = (
    "uuid,meta.create_time,meta.description,meta.tags,"
    "spec.project_uuid,spec.summary,spec.level,spec.finding_metadata,spec.finding_tags,spec.finding_categories"
)


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
        allowed_methods=False,
    )
    adapter = HTTPAdapter(pool_connections=max_pool, pool_maxsize=max_pool, max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update({"Connection": "keep-alive"})
    SESSION = sess


def _do_request(method: str, url: str, **kwargs) -> requests.Response:
    if SESSION is not None:
        return SESSION.request(method, url, **kwargs)
    return requests.request(method, url, **kwargs)


def get_token(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    if token:
        return token
    key = api_key or os.getenv("ENDOR_API_CREDENTIALS_KEY")
    secret = api_secret or os.getenv("ENDOR_API_CREDENTIALS_SECRET")
    if not key or not secret:
        raise Exception(
            "Missing API credentials. Provide --api-key/--api-secret or set "
            "ENDOR_API_CREDENTIALS_KEY and ENDOR_API_CREDENTIALS_SECRET, or provide --token/ENDOR_TOKEN."
        )
    url = f"{API_URL}/auth/api-key"
    payload = {"key": key, "secret": secret}
    headers = {"Content-Type": "application/json"}
    response = _do_request("POST", url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("token")
    raise Exception(f"Failed to get token: {response.status_code}, {response.text}")


def _authorized_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    **kwargs,
) -> requests.Response:
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


def list_secrets_findings(
    namespace: Optional[str] = None,
    token: Optional[str] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """
    Paginate through all Finding objects where spec.finding_categories contains FINDING_CATEGORY_SECRETS.
    """
    ns = namespace or ENDOR_NAMESPACE
    if not ns:
        raise ValueError("Namespace is required. Set ENDOR_NAMESPACE env var or pass namespace argument.")

    bearer_token = get_token(api_key=api_key, api_secret=api_secret, token=token)
    token_box: List[str] = [bearer_token]
    url = f"{API_URL}/namespaces/{ns}/findings"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800",
    }

    all_objects: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None
    page_count = 0

    while True:
        page_count += 1
        params: Dict[str, Any] = {
            "list_parameters.filter": SECRETS_FINDINGS_FILTER,
            "list_parameters.page_size": 500,
            "list_parameters.traverse": "true",
            "list_parameters.mask": FINDINGS_MASK,
        }
        if next_page_token:
            params["list_parameters.page_token"] = next_page_token

        if debug:
            print(f"[debug] findings (secrets): fetching page {page_count} ...")

        response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to list secrets findings (page {page_count}): {response.status_code}, {response.text}")

        data = response.json()
        batch = data.get("list", {}).get("objects", []) or []
        all_objects.extend(batch)

        if debug:
            print(f"[debug] findings (secrets): page {page_count} ok; batch={len(batch)}, total={len(all_objects)}")

        next_page_token = data.get("list", {}).get("response", {}).get("next_page_token")
        if not next_page_token:
            break

    return all_objects


def get_project_name(
    namespace: str,
    project_uuid: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Tuple[str, str]:
    """Return (project_uuid, meta.name or empty string)."""
    if not project_uuid:
        return ("", "")
    url = f"{API_URL}/namespaces/{namespace}/projects/{project_uuid}"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800",
    }
    params = {"get_parameters.mask": "uuid,meta.name"}
    resp = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
    if resp.status_code == 200:
        body = resp.json()
        name = (body.get("meta") or {}).get("name") or ""
        return (project_uuid, name)
    return (project_uuid, "")


def extract_secret_locations(finding: Dict[str, Any]) -> str:
    """Best-effort Secret Location fields from policy results."""
    try:
        results = (
            finding.get("spec", {})
            .get("finding_metadata", {})
            .get("source_policy_info", {})
            .get("results", [])
        )
        locs: List[str] = []
        for r in results:
            if not isinstance(r, dict):
                continue
            loc = (r.get("fields") or {}).get("Secret Location")
            if loc:
                locs.append(str(loc))
        return "; ".join(locs)
    except Exception:
        return ""


def finding_to_row(
    finding: Dict[str, Any],
    project_name_by_uuid: Dict[str, str],
) -> List[Any]:
    meta = finding.get("meta") or {}
    spec = finding.get("spec") or {}
    pu = spec.get("project_uuid") or ""
    tags = meta.get("tags")
    if isinstance(tags, list):
        tags_str = ";".join(str(t) for t in tags)
    else:
        tags_str = json.dumps(tags) if tags is not None else ""

    ft = spec.get("finding_tags")
    if isinstance(ft, list):
        finding_tags_str = ";".join(str(t) for t in ft)
    else:
        finding_tags_str = json.dumps(ft) if ft is not None else ""

    fc = spec.get("finding_categories")
    if isinstance(fc, list):
        finding_categories_str = ";".join(str(t) for t in fc)
    else:
        finding_categories_str = json.dumps(fc) if fc is not None else ""

    return [
        finding.get("uuid", ""),
        pu,
        project_name_by_uuid.get(pu, ""),
        spec.get("summary", ""),
        spec.get("level", ""),
        meta.get("description", ""),
        meta.get("create_time", ""),
        tags_str,
        finding_tags_str,
        finding_categories_str,
        extract_secret_locations(finding),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export secret findings (spec.finding_categories contains FINDING_CATEGORY_SECRETS) to CSV."
    )
    parser.add_argument("--namespace", "-n", default=os.getenv("ENDOR_NAMESPACE"), help="Namespace (or set ENDOR_NAMESPACE)")
    parser.add_argument("--api-key", default=os.getenv("ENDOR_API_CREDENTIALS_KEY"), help="API key")
    parser.add_argument("--api-secret", default=os.getenv("ENDOR_API_CREDENTIALS_SECRET"), help="API secret")
    parser.add_argument("--token", default=os.getenv("ENDOR_TOKEN"), help="Bearer token")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--workers", type=int, default=20, help="Parallel workers for project name API calls")
    args = parser.parse_args()

    if not args.namespace:
        print("Error: --namespace or ENDOR_NAMESPACE is required.")
        sys.exit(1)
    if not args.token and (not args.api_key or not args.api_secret):
        print("Error: Provide --token/ENDOR_TOKEN or both --api-key and --api-secret.")
        sys.exit(1)

    _init_shared_session(max_pool=args.workers)

    try:
        print("Listing secret findings (FINDING_CATEGORY_SECRETS). This may take a few minutes ...")
        findings = list_secrets_findings(
            namespace=args.namespace,
            token=args.token,
            api_key=args.api_key,
            api_secret=args.api_secret,
            debug=args.debug,
        )
        print(f"Found {len(findings)} secret findings.")

        unique_projects = sorted(
            {f.get("spec", {}).get("project_uuid") for f in findings if f.get("spec", {}).get("project_uuid")}
        )

        bearer = get_token(api_key=args.api_key, api_secret=args.api_secret, token=args.token)
        token_box: List[str] = [bearer]
        project_name_by_uuid: Dict[str, str] = {}
        project_lock = threading.Lock()

        def fetch_project(pu: str) -> None:
            try:
                uid, name = get_project_name(args.namespace, pu, token_box, args.api_key, args.api_secret)
                with project_lock:
                    project_name_by_uuid[uid] = name
            except Exception as ex:
                if args.debug:
                    print(f"\nerror resolving project {pu}: {ex}")
                with project_lock:
                    project_name_by_uuid[pu] = ""

        if unique_projects:
            print(f"Resolving {len(unique_projects)} project name(s) with {args.workers} workers ...")
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [executor.submit(fetch_project, pu) for pu in unique_projects]
                done = 0
                total = len(futures)
                for _ in as_completed(futures):
                    done += 1
                    if done % 25 == 0 or done == total:
                        print(f"\rcompleted {done}/{total}", end="", flush=True)
                print()

        os.makedirs("generated_reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ns_safe = (args.namespace or "namespace").replace("/", "_")
        output_path = f"generated_reports/secret_findings_{ns_safe}_{timestamp}.csv"

        header = [
            "finding_uuid",
            "project_uuid",
            "project_name",
            "summary",
            "level",
            "description",
            "create_time",
            "meta_tags",
            "finding_tags",
            "finding_categories",
            "secret_locations",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(header)
            for finding in findings:
                writer.writerow(finding_to_row(finding, project_name_by_uuid))

        print(output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
