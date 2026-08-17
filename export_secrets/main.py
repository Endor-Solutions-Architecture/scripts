import os
import sys
import csv
import json
import argparse
from datetime import datetime
from urllib.parse import quote
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
    "uuid,meta.create_time,meta.description,meta.tags,tenant_meta.namespace,"
    "spec.project_uuid,spec.summary,spec.level,spec.finding_metadata,spec.finding_tags,spec.finding_categories"
)


def _debug_print_response_body(debug: bool, title: str, response: requests.Response) -> None:
    """When debug is on, print HTTP status and full body (pretty-printed JSON if valid)."""
    if not debug:
        return
    print(f"[debug] {title}: HTTP {response.status_code}")
    try:
        parsed = response.json()
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, ValueError):
        print("[debug] Raw body (not JSON or empty):")
        print(response.text if response.text else "(empty)")


def _debug_print_json_data(debug: bool, title: str, data: Any) -> None:
    """When debug is on, print a parsed JSON-serializable structure."""
    if not debug:
        return
    print(f"[debug] {title}")
    try:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except (TypeError, ValueError):
        print(repr(data))


def _extract_count_response_count(data: Dict[str, Any]) -> Optional[int]:
    """Parse count from count_response.count (findings, namespaces, etc.)."""
    cr = data.get("count_response")
    if isinstance(cr, dict):
        c = cr.get("count")
        if isinstance(c, int) and c >= 0:
            return c
    lr = data.get("list") or {}
    resp = lr.get("response") or {}
    for container in (resp, lr):
        for key in (
            "total_count",
            "total_size",
            "count",
            "totalCount",
            "totalSize",
        ):
            v = container.get(key)
            if isinstance(v, int) and v >= 0:
                return v
    ac = resp.get("aggregation_count") or lr.get("aggregation_count")
    if isinstance(ac, dict):
        c = ac.get("count")
        if isinstance(c, int):
            return c
    return None


def get_secrets_findings_total_count(
    namespace: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    debug: bool = False,
) -> Optional[int]:
    """
    Single request: traverse=true + count=true on findings list for namespace (includes children).
    Returns total count if the API exposes it in the list response.
    """
    url = f"{API_URL}/namespaces/{namespace}/findings"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800",
    }
    params: Dict[str, Any] = {
        "list_parameters.filter": SECRETS_FINDINGS_FILTER,
        "list_parameters.traverse": "true",
        "list_parameters.count": "true",
    }
    if debug:
        print("[debug] count query (traverse + count): GET findings ...")
    response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
    if response.status_code != 200:
        _debug_print_response_body(debug, "count query (non-success)", response)
        return None
    try:
        data = response.json()
    except json.JSONDecodeError:
        _debug_print_response_body(debug, "count query (invalid JSON body)", response)
        return None
    total = _extract_count_response_count(data)
    if debug:
        lr = data.get("list") or {}
        resp = lr.get("response") or {}
        print(
            f"[debug] parsed total_count={total}; "
            f"top-level keys={list(data.keys())}; "
            f"list.keys={list(lr.keys())}; "
            f"list.response keys={list(resp.keys())}"
        )
    if total is None and debug:
        _debug_print_json_data(
            debug,
            "count query response body (total not parsed from list.response; full JSON below)",
            data,
        )
    return total


def get_nested_namespaces_total_count(
    root_namespace: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    debug: bool = False,
) -> Optional[int]:
    """
    Same as: endorctl -n <root> api list -r Namespace --traverse --count
    GET /v1/namespaces/{root}/namespaces with traverse + count only.
    """
    ns_segment = quote(root_namespace, safe="")
    url = f"{API_URL}/namespaces/{ns_segment}/namespaces"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800",
    }
    params: Dict[str, Any] = {
        "list_parameters.traverse": "true",
        "list_parameters.count": "true",
    }
    if debug:
        print("[debug] namespace count query (traverse + count): GET .../namespaces ...")
    response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
    if response.status_code != 200:
        _debug_print_response_body(debug, "namespace count query (non-success)", response)
        return None
    try:
        data = response.json()
    except json.JSONDecodeError:
        _debug_print_response_body(debug, "namespace count query (invalid JSON body)", response)
        return None
    total = _extract_count_response_count(data)
    if total is None and debug:
        _debug_print_json_data(debug, "namespace count query response (total not parsed)", data)
    return total


def list_namespaces_under_root(
    root_namespace: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    debug: bool = False,
    *,
    expected_object_total: Optional[int] = None,
) -> List[str]:
    """
    List namespaces via GET /v1/namespaces/{tenant_meta.namespace}/namespaces (traverse).
    Prefer each row's spec.full_name (e.g. scott-learn.testing-cli-integrated); nested list
    meta.name is often only the short segment and cannot be used for /namespaces/{ns}/findings.
    Order matches API page order; duplicate rows are kept if the API returns them.
    """
    ns_segment = quote(root_namespace, safe="")
    url = f"{API_URL}/namespaces/{ns_segment}/namespaces"
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Request-Timeout": "1800",
    }
    names: List[str] = []
    total_list_objects = 0
    skipped_no_name = 0
    # Pagination may use next_page_id or next_page_token depending on API/version.
    next_page_param: Optional[Tuple[str, str]] = None
    page = 0
    while True:
        page += 1
        params: Dict[str, Any] = {
            "list_parameters.mask": "uuid,meta.name,spec.full_name",
            "list_parameters.traverse": "true",
            "list_parameters.page_size": 500,
        }
        if next_page_param:
            params[next_page_param[0]] = next_page_param[1]
        if debug:
            print(f"[debug] namespaces: page {page} ...")
        response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
        if response.status_code != 200:
            _debug_print_response_body(debug, f"namespaces list (non-success, page {page})", response)
            raise Exception(f"Failed to list namespaces (page {page}): {response.status_code}, {response.text}")
        try:
            data = response.json()
        except json.JSONDecodeError:
            _debug_print_response_body(debug, f"namespaces list (invalid JSON, page {page})", response)
            raise Exception(f"Failed to list namespaces (page {page}): invalid JSON response")
        objects = data.get("list", {}).get("objects", []) or []
        n_here = len(objects)
        total_list_objects += n_here
        print(f"  Namespace list page {page}: list.objects[] has {n_here} item(s)")
        for obj in objects:
            full_name = (obj.get("spec") or {}).get("full_name")
            meta_name = (obj.get("meta") or {}).get("name")
            # Prefer fully-qualified name; short meta.name alone yields 403 on findings/projects APIs.
            chosen = full_name if isinstance(full_name, str) and full_name != "" else None
            if chosen is None and isinstance(meta_name, str) and meta_name != "":
                chosen = meta_name
            if chosen is not None:
                names.append(chosen)
                if debug and isinstance(full_name, str) and isinstance(meta_name, str) and full_name != meta_name:
                    print(f"[debug] namespace row: meta.name={meta_name!r} -> spec.full_name={full_name!r}")
            else:
                skipped_no_name += 1
        list_resp = data.get("list", {}).get("response") or {}
        npid = list_resp.get("next_page_id")
        nptok = list_resp.get("next_page_token")
        if npid:
            next_page_param = ("list_parameters.page_id", npid)
        elif nptok:
            next_page_param = ("list_parameters.page_token", nptok)
        else:
            break

    print(
        f"Namespace list API: {total_list_objects} total object(s) in list.objects across {page} page(s)"
        + (f"; {skipped_no_name} object(s) had no usable name" if skipped_no_name else "")
        + "."
    )
    print(
        f"From list.objects: {len(names)} namespace name(s) for scanning "
        f"(prefer spec.full_name; no deduplication)."
    )
    if expected_object_total is not None:
        if total_list_objects != expected_object_total:
            print(
                f"Warning: sum of list.objects lengths ({total_list_objects}) does not match "
                f"traverse+count ({expected_object_total}). Pagination or API semantics may differ."
            )
        else:
            print(
                f"Listed row count matches traverse+count ({expected_object_total})."
            )

    if not names:
        return [root_namespace]
    # Root is not always in the nested child list; include it so secrets on the parent are scanned.
    if root_namespace not in names:
        return [root_namespace] + list(names)
    return list(names)


def paginate_secrets_findings(
    namespace: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    *,
    traverse: bool,
    debug: bool = False,
    progress_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Paginate findings for one namespace; traverse false = this namespace only."""
    url = f"{API_URL}/namespaces/{namespace}/findings"
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
            "list_parameters.traverse": "true" if traverse else "false",
            "list_parameters.mask": FINDINGS_MASK,
        }
        if next_page_token:
            params["list_parameters.page_token"] = next_page_token
        if debug:
            lbl = progress_label or namespace
            print(f"[debug] findings [{lbl}] page {page_count} traverse={traverse} ...")

        response = _authorized_request("GET", url, headers, token_box, api_key, api_secret, params=params)
        if response.status_code != 200:
            _debug_print_response_body(
                debug,
                f"findings list (non-success) namespace={namespace} page={page_count}",
                response,
            )
            raise Exception(
                f"Failed to list secrets findings for namespace={namespace} (page {page_count}): "
                f"{response.status_code}, {response.text}"
            )
        try:
            data = response.json()
        except json.JSONDecodeError:
            _debug_print_response_body(
                debug,
                f"findings list (invalid JSON) namespace={namespace} page={page_count}",
                response,
            )
            raise Exception(
                f"Failed to list secrets findings for namespace={namespace} (page {page_count}): invalid JSON response"
            )
        batch = data.get("list", {}).get("objects", []) or []
        all_objects.extend(batch)
        next_page_token = data.get("list", {}).get("response", {}).get("next_page_token")
        if not next_page_token:
            break
    return all_objects


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


def get_project_name(
    namespace: str,
    project_uuid: str,
    token_box: List[str],
    api_key: Optional[str],
    api_secret: Optional[str],
    debug: bool = False,
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
        try:
            body = resp.json()
        except json.JSONDecodeError:
            _debug_print_response_body(debug, f"get project (invalid JSON) ns={namespace} uuid={project_uuid}", resp)
            return (project_uuid, "")
        name = (body.get("meta") or {}).get("name") or ""
        return (project_uuid, name)
    _debug_print_response_body(debug, f"get project (non-success) ns={namespace} uuid={project_uuid}", resp)
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
    project_name_by_key: Dict[Tuple[str, str], str],
    default_namespace: str,
) -> List[Any]:
    meta = finding.get("meta") or {}
    spec = finding.get("spec") or {}
    pu = spec.get("project_uuid") or ""
    api_ns = (finding.get("tenant_meta") or {}).get("namespace") or default_namespace
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
        project_name_by_key.get((api_ns, pu), ""),
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
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Parallel workers for per-namespace findings fetch and project name lookups",
    )
    args = parser.parse_args()

    if not args.namespace:
        print("Error: --namespace or ENDOR_NAMESPACE is required.")
        sys.exit(1)
    if not args.token and (not args.api_key or not args.api_secret):
        print("Error: Provide --token/ENDOR_TOKEN or both --api-key and --api-secret.")
        sys.exit(1)

    _init_shared_session(max_pool=args.workers)

    try:
        bearer = get_token(api_key=args.api_key, api_secret=args.api_secret, token=args.token)
        token_box: List[str] = [bearer]

        print("Querying total secret findings count (traverse + count on root namespace) ...")
        expected_total = get_secrets_findings_total_count(
            args.namespace,
            token_box,
            args.api_key,
            args.api_secret,
            debug=args.debug,
        )
        if expected_total is not None:
            print(f"Total secret findings (namespace + child namespaces): {expected_total}")
        else:
            print(
                "Could not read total count from the API response "
                "(progress will show findings collected only)."
            )

        print(f"Discovering namespaces under '{args.namespace}' ...")
        api_namespace_count = get_nested_namespaces_total_count(
            args.namespace,
            token_box,
            args.api_key,
            args.api_secret,
            debug=args.debug,
        )
        if api_namespace_count is not None:
            print(
                "Namespaces (traverse + count; same as "
                "`endorctl -n <ns> api list -r Namespace --traverse --count`): "
                f"{api_namespace_count}"
            )
        namespaces = list_namespaces_under_root(
            args.namespace,
            token_box,
            args.api_key,
            args.api_secret,
            debug=args.debug,
            expected_object_total=api_namespace_count,
        )
        print(
            f"{len(namespaces)} namespace(s) to scan "
            "(API list order; prefer spec.full_name; duplicates not removed)."
        )
        print(f"Will fetch findings per namespace: {', '.join(namespaces)}")

        findings: List[Dict[str, Any]] = []
        ns_completed = [0]

        def fetch_ns_findings(ns_name: str) -> Tuple[str, List[Dict[str, Any]]]:
            objs = paginate_secrets_findings(
                ns_name,
                token_box,
                args.api_key,
                args.api_secret,
                traverse=False,
                debug=args.debug,
            )
            return ns_name, objs

        pool_ns = max(1, min(args.workers, len(namespaces)))
        print(f"Fetching secret findings per namespace with {pool_ns} worker(s) ...")
        with ThreadPoolExecutor(max_workers=pool_ns) as executor:
            futures = [executor.submit(fetch_ns_findings, ns) for ns in namespaces]
            for fut in as_completed(futures):
                ns_name, objs = fut.result()
                findings.extend(objs)
                ns_completed[0] += 1
                n = len(findings)
                tot_s = str(expected_total) if expected_total is not None else "?"
                print(
                    f"\rProgress: {n}/{tot_s} findings | namespaces done {ns_completed[0]}/{len(namespaces)} "
                    f"(last: {ns_name}, +{len(objs)})",
                    end="",
                    flush=True,
                )
        print()
        print(f"Collected {len(findings)} secret finding record(s).")
        if expected_total is not None and len(findings) != expected_total:
            print(
                f"Note: collected count ({len(findings)}) differs from upfront total ({expected_total}). "
                "This can happen if findings changed during the run or if count/list semantics differ slightly."
            )

        pair_set = set()
        for f in findings:
            pu = (f.get("spec") or {}).get("project_uuid")
            if not pu:
                continue
            api_ns = (f.get("tenant_meta") or {}).get("namespace") or args.namespace
            pair_set.add((api_ns, pu))
        project_pairs = sorted(pair_set)

        project_name_by_key: Dict[Tuple[str, str], str] = {}
        project_lock = threading.Lock()

        def fetch_project(pair: Tuple[str, str]) -> None:
            api_ns, pu = pair
            try:
                uid, name = get_project_name(
                    api_ns, pu, token_box, args.api_key, args.api_secret, debug=args.debug
                )
                with project_lock:
                    project_name_by_key[(api_ns, uid)] = name
            except Exception as ex:
                if args.debug:
                    print(f"\nerror resolving project {pu} in {api_ns}: {ex}")
                with project_lock:
                    project_name_by_key[(api_ns, pu)] = ""

        if project_pairs:
            print(f"Resolving {len(project_pairs)} project name(s) with {args.workers} workers ...")
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures_p = [executor.submit(fetch_project, p) for p in project_pairs]
                done = 0
                total_p = len(futures_p)
                for _ in as_completed(futures_p):
                    done += 1
                    if done % 25 == 0 or done == total_p:
                        print(f"\rcompleted {done}/{total_p}", end="", flush=True)
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
                writer.writerow(finding_to_row(finding, project_name_by_key, args.namespace))

        print(output_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
