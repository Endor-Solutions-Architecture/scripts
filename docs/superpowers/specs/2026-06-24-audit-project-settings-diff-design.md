# Design: audit_project_settings diff

**Date:** 2026-06-24
**Status:** Approved

## Overview

Add `diff.py` to the `audit_project_settings/` folder. Takes two JSON files produced by `main.py` (one per project) and outputs what's in A but missing from B — giving a migration checklist of policies and scan profiles that need to be recreated in the destination.

## Folder Layout

```
audit_project_settings/
├── main.py              # unchanged
├── diff.py              # new standalone diff script
├── generated_reports/   # already exists (gitignored)
├── requirements.txt     # unchanged — diff.py uses only stdlib
└── README.md            # updated with diff.py section
```

No new runtime dependencies — `diff.py` uses only stdlib (`json`, `argparse`, `pathlib`, `datetime`).

## CLI Interface

```
python diff.py <audit_a.json> <audit_b.json> [--output-dir <dir>]
```

| Argument | Required | Description |
|---|---|---|
| `audit_a` | Yes | Path to the source audit JSON (the "reference" project) |
| `audit_b` | Yes | Path to the destination audit JSON (the project being migrated to) |
| `--output-dir` | No | Directory for output files. Default: `generated_reports/` |

## Matching Logic

Policies and scan profiles are matched **by name only** across the full namespace hierarchy:

1. Flatten all policy names from B into a set (across all namespace levels)
2. Flatten all scan profile names from B into a set
3. Walk every namespace level in A — any policy name not in B's set → missing
4. Walk every namespace level in A — any scan profile name not in B's set → missing
5. Group missing policies by `policy_type` for output

Matching is case-sensitive and exact. UUIDs are not used for matching (they differ across namespaces). The source namespace of each missing item is preserved in the output for reference.

## Output

Both files are always written in a single run. The text summary is also printed to stdout.

### File naming

```
generated_reports/diff_audit.<timestamp>.json
generated_reports/diff_audit.<timestamp>.txt
```

Timestamp format: `YYYYMMDD_HHMMSS`.

### JSON schema

```json
{
  "meta": {
    "source_a": {
      "namespace":    string,
      "project_name": string,
      "project_uuid": string
    },
    "source_b": {
      "namespace":    string,
      "project_name": string,
      "project_uuid": string
    }
  },
  "missing_policies": [
    {
      "name":             string,
      "policy_type":      string,
      "source_namespace": string,
      "disabled":         bool,
      "url":              string
    }
  ],
  "missing_scan_profiles": [
    {
      "name":             string,
      "source_namespace": string,
      "is_default":       bool
    }
  ],
  "summary": {
    "missing_policy_count":       int,
    "missing_scan_profile_count": int
  }
}
```

### Text format

```
Diff: <a_namespace> (<a_project_uuid>) → <b_namespace> (<b_project_uuid>)

Policies missing from B (N):
  POLICY_TYPE_EXCEPTION (n):
    - <name>  [<source_namespace>] <url>
  POLICY_TYPE_ADMISSION (n):
    - <name>  [<source_namespace>] <url>

Scan profiles missing from B (N):
  - <name>  [<source_namespace>]

Summary: N missing policies, N missing scan profiles.
Output: generated_reports/diff_audit.<timestamp>.json
        generated_reports/diff_audit.<timestamp>.txt
```

When a category has zero missing items, the line reads: `Policies missing from B (0): none`

## Error Handling

- Either input file not found → print error to stderr, exit 1
- Invalid JSON in either file → print error to stderr, exit 1
- Missing required keys in the audit JSON (not a valid audit output) → print error to stderr, exit 1
- `--output-dir` is created if it does not exist

## Prerequisites

Same as `main.py`: Python 3.10+. No additional packages needed.
