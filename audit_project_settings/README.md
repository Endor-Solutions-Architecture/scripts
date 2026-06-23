# audit_project_settings

Audits all policies and scan profiles that are visible to an Endor Labs project, tracing each one through the namespace hierarchy to explain **why** it applies. Outputs structured JSON suitable for saving, diffing, or piping into `jq`.

Primary use case: **project migration** — run this before moving a project to a new namespace to get a complete inventory of every policy and scan profile that needs to be recreated or reattached in the destination.

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt`
- `endorctl` authenticated (or set `ENDOR_TOKEN`, or pass `--token`)
- `jq` on your `PATH` (optional — for filtering the JSON output)

## Usage

```
python main.py [options] <namespace> <project-uuid> [api-url]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `namespace` | Yes | The project's full namespace (e.g. `acme.backend.api`) |
| `project-uuid` | Yes | The project's UUID |
| `api-url` | No | API base URL. Defaults to `$ENDOR_API` if set, otherwise `https://api.endorlabs.com` |

### Options

| Option | Description |
|---|---|
| `--all` | Include policies that do **not** match this project's tags or that are scope-excluded. Scan profiles always appear regardless. Default: only applying policies are shown. |
| `--policy-types <types>` | Comma-separated list of policy types to include. Default: all types. See [Policy Types](#policy-types) below. |
| `--token <token>` | Explicit bearer token. Overrides `ENDOR_TOKEN` env var and `endorctl auth`. |

## Policy Types

The `--policy-types` flag accepts short aliases or full API enum names:

| Alias | API enum | What it does |
|---|---|---|
| `exception` | `POLICY_TYPE_EXCEPTION` | Dismisses findings — exempts specific findings from action policies |
| `action` | `POLICY_TYPE_ADMISSION` | **Blocks CI/CD pipelines** — "Break the Build" (exit 128) or "Warn" (exit 0) |
| `finding` | `POLICY_TYPE_USER_FINDING` | Creates/raises findings — enables or defines custom finding rules |
| `notification` | `POLICY_TYPE_NOTIFICATION` | Sends alerts (Jira, Slack, etc.) when findings match criteria |
| `admission` | `POLICY_TYPE_ADMISSION` | Same as `action` (full alias for the API enum name) |
| `remediation` | `POLICY_TYPE_REMEDIATION` | Auto-remediates findings when a safe upgrade is available |

Full API enum names (e.g. `POLICY_TYPE_EXCEPTION`) are also accepted directly.

## How Namespace Inheritance Works

Endor Labs namespaces are dot-delimited hierarchies. A project in `acme.backend.api` is also subject to policies defined in `acme.backend` and `acme`. This script queries every level — root to own — and reports each policy's source namespace and scope.

Each policy's `reason` field explains exactly why it applies (or doesn't):

| Reason | Meaning |
|---|---|
| `all projects in namespace` | No `project_selector` set — applies to every project in that namespace |
| `tag-scoped match on: <tags>` | Policy has a `project_selector` and this project has a matching tag |
| `tag-scoped no match (selector: …)` | Policy has a `project_selector` but this project's tags don't overlap |
| `excluded — listed in project_exceptions` | This project's UUID is explicitly excluded from the policy |

## Output Schema

```
{
  "meta": {
    "namespace":     string,
    "project_uuid":  string,
    "api":           string,
    "show_all":      bool,
    "policy_types":  array | "all"
  },
  "project": {
    "name":  string,
    "uuid":  string,
    "tags":  array
  },
  "namespaces": [
    {
      "namespace":  string,
      "scope":      "own" | "parent",
      "policies": [
        {
          "uuid":         string,
          "name":         string,
          "policy_type":  string,
          "applies":      bool,
          "reason":       string,
          "disabled":     bool,
          "url":          string
        }
      ],
      "scan_profiles": [
        {
          "uuid":        string,
          "name":        string,
          "is_default":  bool,
          "applies":     bool,
          "reason":      string
        }
      ]
    }
  ]
}
```

Note: `ScanProfile` resources have no `project_selector` — all scan profiles in a namespace (and its parents) apply to every project in that namespace.

## Examples

### Basic audit — only items that apply

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Save to file for migration reference

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 > audit.json
```

### Exception and action policies only

```bash
python main.py --policy-types exception,action \
  acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Include non-matching policies (full namespace inventory)

```bash
python main.py --all --policy-types exception,action \
  acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Run against staging

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  https://api.staging.endorlabs.com
```

### Extract just the policy names and URLs that apply

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  | jq '.namespaces[] | {ns: .namespace, scope: .scope, policies: [.policies[] | {name, url, policy_type}]}'
```

### Count applying policies per namespace level

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  | jq '.namespaces[] | {namespace, policy_count: (.policies | length), profile_count: (.scan_profiles | length)}'
```

---

## Diff: Comparing Two Projects

`diff.py` takes two audit JSON files (produced by `main.py`) and shows what policies and scan profiles are in A but missing from B — giving you a migration checklist.

### Usage

```
python diff.py <audit_a.json> <audit_b.json> [--output-dir <dir>]
```

| Argument | Required | Description |
|---|---|---|
| `audit_a` | Yes | Path to source audit JSON (the reference project) |
| `audit_b` | Yes | Path to destination audit JSON (the target project) |
| `--output-dir` | No | Output directory. Default: `generated_reports/` |

Both a JSON result and a text summary are always written. The text summary is also printed to the terminal.

### Typical migration workflow

```bash
# 1. Audit the source project
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 > audit_source.json

# 2. Audit the destination project
python main.py acme.newteam.api b2c3d4e5f6a7b8c9d0e1f2a3 > audit_dest.json

# 3. See what needs to be recreated in the destination
python diff.py audit_source.json audit_dest.json
```

### Output files

```
generated_reports/diff_audit.<timestamp>.json   # structured diff (pipeable)
generated_reports/diff_audit.<timestamp>.txt    # human-readable checklist
```

### Example terminal output

```
Diff: acme.backend.api (a1b2c3d4e5f6a7b8c9d0e1f2) → acme.newteam.api (b2c3d4e5f6a7b8c9d0e1f2a3)

Policies missing from B (2):
  POLICY_TYPE_ADMISSION (1):
    - Break the Build: Critical CVEs  [acme.backend] https://app.endorlabs.com/t/acme.backend/policies/...
  POLICY_TYPE_EXCEPTION (1):
    - Exception: Log4j  [acme]

Scan profiles missing from B (0): none

Summary: 2 missing policies, 0 missing scan profiles.
Output: generated_reports/diff_audit.20260624_103000.json
        generated_reports/diff_audit.20260624_103000.txt
```
