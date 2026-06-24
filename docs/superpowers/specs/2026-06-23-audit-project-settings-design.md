# Design: audit_project_settings

**Date:** 2026-06-23
**Status:** Approved

## Overview

Migrate `audit-project-settings` (bash) from the monorepo into this repository as a proper Python script following established repo conventions. The script audits all policies and scan profiles that apply to an Endor Labs project, tracing each one through the namespace hierarchy to explain why it applies. Outputs structured JSON suitable for saving, diffing, or piping into `jq`.

Primary use case: **project migration** — run before moving a project to a new namespace to get a complete inventory of every policy and scan profile that needs to be recreated or reattached in the destination.

## Folder Layout

```
audit_project_settings/
├── main.py          # Python rewrite of the bash script
├── requirements.txt # requests~=2.32
└── README.md        # adapted from audit-project-settings.md
```

## Authentication

Follows the `dependency_resolution_summary` pattern — priority order:

1. `--token` CLI flag
2. `ENDOR_TOKEN` environment variable
3. `endorctl auth --print-access-token` (requires endorctl authenticated)

A clear `AuthError` is raised if none of the three sources yields a token.

## CLI Interface

```
python main.py [options] <namespace> <project-uuid> [api-url]
```

| Argument | Required | Description |
|---|---|---|
| `namespace` | Yes | Full namespace (e.g. `acme.backend.api`) |
| `project-uuid` | Yes | The project's UUID |
| `api-url` | No | API base URL. Defaults to `ENDOR_API` env var, then `https://api.endorlabs.com` |

| Option | Description |
|---|---|
| `--all` | Include policies/profiles that do not apply to this project |
| `--policy-types <types>` | Comma-separated list of policy type aliases or full enum names |
| `--token <token>` | Explicit bearer token (overrides env/endorctl) |

Policy type aliases (same as original):

| Alias | API enum |
|---|---|
| `exception` | `POLICY_TYPE_EXCEPTION` |
| `action` | `POLICY_TYPE_ADMISSION` |
| `finding` | `POLICY_TYPE_USER_FINDING` |
| `notification` | `POLICY_TYPE_NOTIFICATION` |
| `admission` | `POLICY_TYPE_ADMISSION` |
| `remediation` | `POLICY_TYPE_REMEDIATION` |

## REST API Calls

Replaces `endorctl api get/list` with direct HTTP calls:

| bash original | Python replacement |
|---|---|
| `endorctl api get -r Project --uuid $UUID -n $NS` | `GET /v1/namespaces/{ns}/projects/{uuid}` |
| `endorctl api list -r Policy -n $NS --list-all` | `GET /v1/namespaces/{ns}/policies` (paginated) |
| `endorctl api list -r ScanProfile -n $NS --list-all` | `GET /v1/namespaces/{ns}/scan-profiles` (paginated) |

Pagination: walk `response.list_response.next_page_token` until empty, collecting all objects.

Server-side policy type filter passed as `filter=spec.policy_type in [...]` query parameter when `--policy-types` is set.

## Apply Logic (Python)

Replaces all `jq` processing. For each policy:

1. If project UUID is in `spec.project_exceptions` → `applies=False`, reason `"excluded — listed in project_exceptions"`
2. Elif `spec.project_selector` is empty → `applies=True`, reason `"all projects in namespace"`
3. Elif any selector tag matches a project tag → `applies=True`, reason `"tag-scoped match on: <tags>"`
4. Else → `applies=False`, reason `"tag-scoped no match (selector: …)"`

Scan profiles have no project selector — always `applies=True`.

## Output Schema

Identical JSON to the bash original:

```json
{
  "meta": { "namespace", "project_uuid", "api", "show_all", "policy_types" },
  "project": { "name", "uuid", "tags" },
  "namespaces": [
    {
      "namespace", "scope",
      "policies": [{ "uuid", "name", "policy_type", "applies", "reason", "disabled", "url" }],
      "scan_profiles": [{ "uuid", "name", "is_default", "applies", "reason" }]
    }
  ]
}
```

When `--all` is not set, namespaces entries are filtered to only include `applies=True` items. Output is `json.dumps(..., indent=2)` to stdout.

## Error Handling

- Missing required args → `argparse` prints usage and exits 1
- Project not found → print error to stderr, exit 1
- API HTTP error → raise `RuntimeError` with status and body
- Auth failure → raise `AuthError` with actionable message

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt` (installs `requests`)
- `endorctl` authenticated (or `ENDOR_TOKEN` set, or `--token` passed)
