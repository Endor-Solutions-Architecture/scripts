import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

DEFAULT_API_URL = "https://api.endorlabs.com"


class AuthError(RuntimeError):
    """Raised when no token can be resolved."""


def resolve_token(explicit: str | None) -> str:
    """Return a JWT. Priority: explicit → ENDOR_TOKEN → endorctl auth."""
    if explicit:
        return explicit
    env = os.environ.get("ENDOR_TOKEN")
    if env:
        return env
    try:
        result = subprocess.run(
            ["endorctl", "auth", "--print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AuthError(
            "endorctl is not installed. Install it or pass --token / set ENDOR_TOKEN."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AuthError(
            "endorctl auth failed — run `endorctl auth login` first, "
            "or set ENDOR_TOKEN. stderr:\n" + (exc.stderr or "")
        ) from exc
    return result.stdout.strip()


def fetch_project(api_url: str, namespace: str, uuid: str, token: str) -> dict:
    """GET /v1/namespaces/{namespace}/projects/{uuid}. Exits 1 if not found."""
    url = f"{api_url.rstrip('/')}/v1/namespaces/{namespace}/projects/{uuid}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code >= 400:
        print(f"ERROR: Could not fetch project {uuid} in namespace {namespace} "
              f"(HTTP {resp.status_code})", file=sys.stderr)
        sys.exit(1)
    return resp.json()


POLICY_TYPE_ALIASES: dict[str, str] = {
    "EXCEPTION": "POLICY_TYPE_EXCEPTION",
    "ACTION": "POLICY_TYPE_ADMISSION",
    "FINDING": "POLICY_TYPE_USER_FINDING",
    "NOTIFICATION": "POLICY_TYPE_NOTIFICATION",
    "ADMISSION": "POLICY_TYPE_ADMISSION",
    "REMEDIATION": "POLICY_TYPE_REMEDIATION",
}


def normalize_policy_types(raw: str) -> list[str]:
    """Convert comma-separated aliases/full names to POLICY_TYPE_* list."""
    if not raw:
        return []
    result = []
    for token in raw.split(","):
        upper = token.strip().upper()
        if upper in POLICY_TYPE_ALIASES:
            result.append(POLICY_TYPE_ALIASES[upper])
        elif upper.startswith("POLICY_TYPE_"):
            result.append(upper)
        else:
            print(f"WARNING: unknown policy type '{token.strip()}' — skipped. "
                  "Valid aliases: exception, action, finding, notification, admission, remediation",
                  file=sys.stderr)
    return result


def build_ns_hierarchy(namespace: str) -> list[str]:
    """'a.b.c' → ['a', 'a.b', 'a.b.c']"""
    parts = namespace.split(".")
    levels = []
    for i in range(len(parts)):
        levels.append(".".join(parts[: i + 1]))
    return levels


def fetch_all_paged(url: str, token: str, params: dict | None = None) -> list[dict]:
    """GET url with pagination, collecting all list.objects entries."""
    headers = {"Authorization": f"Bearer {token}"}
    params = dict(params or {})
    params.setdefault("list_parameters.page_size", 25)
    objects: list[dict] = []
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
        body = resp.json()
        objects.extend(body.get("list", {}).get("objects") or [])
        next_token = (body.get("list", {}).get("response", {}) or {}).get("next_page_token")
        if not next_token:
            break
        params["list_parameters.page_token"] = next_token
    return objects


def determine_applies(
    policy: dict, project_uuid: str, project_tags: list[str]
) -> dict:
    """Return {applies, reason} for a policy against a project."""
    spec = policy.get("spec", {}) or {}
    exceptions = spec.get("project_exceptions") or []
    selector = spec.get("project_selector") or []

    if project_uuid in exceptions:
        return {"applies": False, "reason": "excluded — listed in project_exceptions"}
    if not selector:
        return {"applies": True, "reason": "all projects in namespace"}

    matched = [t for t in selector if t in project_tags]
    if matched:
        return {"applies": True, "reason": "tag-scoped match on: " + ", ".join(matched)}
    return {"applies": False, "reason": f"tag-scoped no match (selector: {', '.join(selector)})"}


def build_policy_entry(
    policy: dict, applies: dict, app_base: str, query_ns: str
) -> dict:
    """Build a single policy output entry."""
    return {
        "uuid": policy.get("uuid", ""),
        "name": (policy.get("meta") or {}).get("name", ""),
        "policy_type": (policy.get("spec") or {}).get("policy_type", ""),
        "applies": applies["applies"],
        "reason": applies["reason"],
        "disabled": (policy.get("spec") or {}).get("disable", False),
        "url": f"{app_base}/t/{query_ns}/policies/{policy.get('uuid', '')}",
    }


def build_profile_entry(profile: dict) -> dict:
    """Build a single scan profile output entry."""
    return {
        "uuid": profile.get("uuid", ""),
        "name": (profile.get("meta") or {}).get("name", ""),
        "is_default": (profile.get("spec") or {}).get("is_default", False),
        "applies": True,
        "reason": "all projects in namespace (no project-level selector)",
    }


def _app_base(api_url: str) -> str:
    """'https://api.endorlabs.com' → 'https://app.endorlabs.com'"""
    return api_url.replace("//api.", "//app.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit policies and scan profiles that apply to an Endor Labs project."
    )
    parser.add_argument("namespace", help="Project's full namespace (e.g. org.repo.name)")
    parser.add_argument("project_uuid", help="Project UUID")
    parser.add_argument(
        "api_url",
        nargs="?",
        default=os.environ.get("ENDOR_API", DEFAULT_API_URL),
        help="API base URL (default: $ENDOR_API or https://api.endorlabs.com)",
    )
    parser.add_argument("--all", dest="show_all", action="store_true",
                        help="Include policies/profiles that do not apply to this project")
    parser.add_argument("--policy-types", default="",
                        help="Comma-separated policy type aliases or full enum names")
    parser.add_argument("--token", default=None,
                        help="Override bearer token (overrides ENDOR_TOKEN / endorctl)")
    parser.add_argument(
        "--output",
        default=None,
        help="Save output JSON to this path instead of the default generated_reports/audit_<namespace>_<uuid>.json",
    )
    args = parser.parse_args(argv)

    try:
        token = resolve_token(args.token)
    except AuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    project = fetch_project(args.api_url, args.namespace, args.project_uuid, token)
    project_name = (project.get("meta") or {}).get("name", "")
    project_tags = (project.get("meta") or {}).get("tags") or []

    normalized_types = normalize_policy_types(args.policy_types)
    ns_hierarchy = build_ns_hierarchy(args.namespace)
    app_base = _app_base(args.api_url)

    base_url = args.api_url.rstrip("/")
    policy_params: dict = {}
    if normalized_types:
        type_list = ", ".join(normalized_types)
        policy_params["list_parameters.filter"] = f"spec.policy_type in [{type_list}]"

    ns_entries = []
    for query_ns in ns_hierarchy:
        scope = "own" if query_ns == args.namespace else "parent"

        policies = fetch_all_paged(
            f"{base_url}/v1/namespaces/{query_ns}/policies",
            token,
            dict(policy_params),
        )
        profiles = fetch_all_paged(
            f"{base_url}/v1/namespaces/{query_ns}/scan-profiles",
            token,
        )

        policy_entries = [
            build_policy_entry(p, determine_applies(p, args.project_uuid, project_tags), app_base, query_ns)
            for p in policies
        ]
        profile_entries = [build_profile_entry(p) for p in profiles]

        ns_entries.append({
            "namespace": query_ns,
            "scope": scope,
            "policies": policy_entries,
            "scan_profiles": profile_entries,
        })

    output = {
        "meta": {
            "namespace": args.namespace,
            "project_uuid": args.project_uuid,
            "api": args.api_url,
            "show_all": args.show_all,
            "policy_types": normalized_types if normalized_types else "all",
        },
        "project": {
            "name": project_name,
            "uuid": args.project_uuid,
            "tags": project_tags,
        },
        "namespaces": ns_entries,
    }

    if not args.show_all:
        output["namespaces"] = [
            {
                **ns,
                "policies": [p for p in ns["policies"] if p["applies"]],
                "scan_profiles": [p for p in ns["scan_profiles"] if p["applies"]],
            }
            for ns in output["namespaces"]
        ]

    # print(json.dumps(output, indent=2))

    save_path = args.output or os.path.join(
        "generated_reports", f"audit_{args.namespace}_{args.project_uuid}.json"
    )
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_text(json.dumps(output, indent=2))
    print(f"Output: {save_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
