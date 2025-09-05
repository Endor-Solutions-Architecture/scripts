## delete_excluded_packages

CLI to find and optionally delete Endor PackageVersions whose `spec.relative_path` matches excluded-path patterns. Patterns can come from a Scan Profile or be provided directly. Uses `endorctl`.

### Prerequisites

- `endorctl` installed and authenticated
- Python 3.9+

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

```bash
python endor_delete_excluded_packages.py <namespace> \
  (--scan-profile-uuid <scan_profile_uuid> | --exclude-pattern "<glob>") \
  [--project-uuid <project_uuid>] \
  [--no-dry-run] \
  [--timeout <seconds>] \
  [--debug]
```

### What it does

- Dry run by default: prints `namespace`, `uuid`, and `name` for matching PackageVersions
- With `--no-dry-run`: deletes the matching PackageVersions via `endorctl`
- If `--project-uuid` is provided, only PackageVersions where `spec.project_uuid == <project_uuid>` are considered
- When `--scan-profile-uuid` is used, patterns are read from `spec.automated_scan_parameters.excluded_paths`
- When `--exclude-pattern` is used, a single shell-style glob (e.g., `tests/**`, `**/*.spec.*`) is applied
- Patterns are matched against `spec.relative_path` with POSIX-style separators (`/`); leading `./` or `/` is ignored

### Examples

Dry run using a Scan Profile's excluded paths:
```bash
python endor_delete_excluded_packages.py scott-learn \
  --scan-profile-uuid 00000000-0000-0000-0000-000000000000
```

Actually delete matches from that profile:
```bash
python endor_delete_excluded_packages.py scott-learn \
  --scan-profile-uuid 00000000-0000-0000-0000-000000000000 \
  --no-dry-run
```

Limit to a specific project:
```bash
python endor_delete_excluded_packages.py scott-learn \
  --scan-profile-uuid 00000000-0000-0000-0000-000000000000 \
  --project-uuid 11111111-1111-1111-1111-111111111111
```

Use a one-off glob pattern (no scan profile):
```bash
python endor_delete_excluded_packages.py scott-learn \
  --exclude-pattern "docs/**" \
  --no-dry-run
```

Increase timeout and enable debug logging:
```bash
python endor_delete_excluded_packages.py scott-learn \
  --scan-profile-uuid 00000000-0000-0000-0000-000000000000 \
  --timeout 60 \
  --debug
```

### Exit codes

- `0`: success (including dry-run with zero matches)
- `1`: completed deletions with at least one failure
- `2`: failed to fetch the requested Scan Profile

### Implementation notes

- Fetch Scan Profile:
  - `endorctl -n {namespace} api get -r ScanProfile --uuid={scan_profile_uuid}`
- List PackageVersions (optionally filtered by project):
  - `endorctl -n {namespace} api list -r PackageVersion --list-all --filter="context.type==CONTEXT_TYPE_MAIN"`
  - With project: `--filter="context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=={project_uuid}"`
- For entries lacking `spec.relative_path` in the list output, the script hydrates by fetching each object by UUID
- Delete PackageVersion:
  - `endorctl -n {namespace} api delete -r PackageVersion --uuid=<uuid>`

### Safety

Deletions are irreversible. Start with a dry run, verify the list, and then repeat with `--no-dry-run` if the matches look correct.