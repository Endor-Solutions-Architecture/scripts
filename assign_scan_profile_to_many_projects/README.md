# Bulk Scan Profile configuration

Assign a Scan Profile to many Endor Labs projects from a CSV, or clear an
explicit bind so projects inherit the tenant’s **default** Scan Profile.

| File | Role |
|------|------|
| [`csv-bulk-set-scanprofile.py`](csv-bulk-set-scanprofile.py) | Tool |
| This README | Customer runbook |

## 1. Install

Python **3.11+** recommended. Create a virtual environment and install the SDK
from PyPI:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install endorlabs
```

Optional (if you already use [uv](https://docs.astral.sh/uv/)):

```bash
uv venv
uv pip install endorlabs
# or: uv add endorlabs   # inside an existing uv project
```

Package: [endorlabs on PyPI](https://pypi.org/project/endorlabs/).

## 2. Credentials

Set environment variables (shell or a local `.env` your process loads):

| Variable | Purpose |
|----------|---------|
| `ENDOR_API_CREDENTIALS_KEY` + `ENDOR_API_CREDENTIALS_SECRET` | API key pair (common for automation) |
| **or** `ENDOR_TOKEN` | Bearer token |
| `ENDOR_NAMESPACE` | Optional default for `-n` |

Do not mix API key and bearer token in the same environment.

| Credential type | Dry-run (default) | `--apply` |
|-----------------|-------------------|-----------|
| Tenant API key / SSO with Project **update** | Yes | Yes |
| Privileged-read / admin-read only | Yes | **No** — omit `--apply` |

Always dry-run first and review the result CSV.

## 3. CSV format

Header row required. At least one identifier column per row:

| Column | Purpose |
|--------|---------|
| `project_uuid` | Preferred — exact Project UUID |
| `repo` | `owner/repo` (GitHub-style slug) |
| `project_name` | Full URL or `meta.name` (e.g. `https://github.com/org/repo.git`) |
| `namespace` | Optional hint if UUID lookup needs a child namespace |
| `scan_profile_uuid` | Optional; status is always refreshed from the API |

Aliases accepted: `uuid`, `repository`, `slug`, `url`, `ns`, etc.

```csv
repo,project_uuid,project_name,namespace
acme/app-one,0123456789abcdef01234567,https://github.com/acme/app-one.git,acme
acme/app-two,,https://github.com/acme/app-two.git,acme
```

## 4. Run

With the venv activated (after `pip install endorlabs`):

```bash
# Dry-run: next 35 projects not already on the target profile
python csv-bulk-set-scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> \
  -b 35 \
  -n <tenant>

# Apply (requires Project update permission)
python csv-bulk-set-scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> \
  -b 35 \
  -n <tenant> \
  --apply

# Clear explicit binds → inherit tenant is_default Scan Profile
python csv-bulk-set-scanprofile.py projects.csv \
  --clear \
  -b 35 \
  -n <tenant> \
  --apply

# Assign and immediately queue App rescans
python csv-bulk-set-scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> \
  -b 35 \
  -n <tenant> \
  --apply \
  --rescan

# Rescan only (profiles already set)
python csv-bulk-set-scanprofile.py projects.csv \
  --rescan-only \
  -b 35 \
  -n <tenant> \
  --apply
```

Optional `uv` form (same flags):

```bash
uv run --env-file .env python csv-bulk-set-scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> -b 35 -n <tenant>
```

On Windows PowerShell, use backticks for line continuation if you split lines.

## 5. Flags

| Flag | Description |
|------|-------------|
| `csv` | Path to the project list |
| `-sp` / `--scan-profile` | Target ScanProfile **UUID** or **name** |
| `--clear` | Clear `scan_profile_uuid` (inherit default). Mutually exclusive with `-sp` |
| `-b` / `--batch` | Max projects to change among rows **not already** on the target (default `35`) |
| `-n` / `--tenant` | Tenant root (default: `ENDOR_NAMESPACE`) |
| `--apply` | Perform updates; omit for dry-run |
| `--rescan` | After a successful profile assign/clear (`--apply`), also queue an App **full rescan** (same as UI **Rescan Project**: `processing_status.scan_state=SCAN_STATE_REQUEST_FULL_RESCAN`). Dry-run reports `would_rescan` |
| `--rescan-only` | Do not change profiles; only queue rescans for resolved CSV rows (honors `-b`). Mutually exclusive with `-sp` / `--clear` |
| `--workers` | Parallel resolve workers (default `16`) |
| `--results-dir` | Result CSV directory (default: `<csv_dir>/bulk_set_results`) |

### `-sp Default` vs `--clear`

If a Scan Profile is **named** `Default`, `-sp Default` **binds** that profile’s UUID.

`--clear` sets `scan_profile_uuid` to empty so the platform **inherits** whichever profile has `is_default: true`. Those are different wire states even when the named profile is also the default.

## 6. Behavior

1. Resolve the target ScanProfile (or clear mode) under the tenant with hierarchy traverse.
2. Resolve each CSV row to a live Project (UUID preferred; otherwise name/URL search).
3. Skip rows already on the target (or already unbound when using `--clear`).
4. Select the first `-b` remaining rows for this run; mark the rest `beyond_batch`.
5. Dry-run prints `would_update`; `--apply` updates only `spec.scan_profile_uuid`.
6. With `--rescan` (or `--rescan-only`), queues App full rescans via `processing_status.scan_state`.
7. Writes a timestamped result CSV with per-row `action`, `status`, `rescan_status`, and `error`.

Re-run the same command after each batch: already-updated rows are skipped automatically.

## 7. Result CSV statuses

| Status | Meaning |
|--------|---------|
| `would_update` | Dry-run: would change this project |
| `updated` | Apply succeeded |
| `already_set` | Already on target (or already unbound for `--clear`) |
| `beyond_batch` | Eligible but outside this `-b` window |
| `resolve_error` | Project not found / ambiguous / API error |
| `error` | Apply failed (see `error` column) |

## Tips

- Prefer `project_uuid` in the CSV for large estates.
- Keep batches modest (e.g. 35) so you can validate scans between runs.
- Changing the tenant’s **default** Scan Profile itself is out of scope for this script and affects every unbound project — do that deliberately in the UI/API, not via this tool.
- Support contact: your Endor Labs account team or [docs.endorlabs.com](https://docs.endorlabs.com/).
