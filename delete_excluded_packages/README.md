## delete_excluded_packages

CLI to find and optionally delete Endor PackageVersions whose `spec.dependency_files` match a scan profile's exclude-path patterns. Uses `endorctl`.

### Prerequisites

- `endorctl` installed and authenticated.

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

```bash
python endor_delete_excluded_packages.py <namespace> \
  --scan-profile-uuid <scan_profile_uuid> \
  [--project-uuid <project_uuid>] \
  [--no-dry-run]
```

- Prints `tenant_meta.namespace`, `uuid`, and `meta.name` of matching PackageVersions.
- When `--no-dry-run` is passed, the script deletes those PackageVersions using `endorctl`.
- If `--project-uuid` is provided, only PackageVersions where `meta.parent_uuid == <project_uuid>` are considered.

### Notes

- The script fetches the Scan Profile via:
  - `endorctl -n {namespace} api get -r ScanProfile --uuid={scan_profile_uuid}`
- The script lists PackageVersions via:
  - `endorctl -n {namespace} api get -r PackageVersion --list-all --filter="context.type==CONTEXT_TYPE_MAIN"`
  - If project provided: `--filter="context.type==CONTEXT_TYPE_MAIN and meta.parent_uuid=={project_uuid}"`
- Matching is done via glob/regex; if a pattern is prefixed `regex:`, it is treated as a regular expression. 