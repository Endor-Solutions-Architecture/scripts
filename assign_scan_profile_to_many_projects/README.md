# Assign Scan Profile to Many Projects

Bulk-assign a [Scan Profile](https://docs.endorlabs.com/scan/scan-profiles/) to
many Endor Labs projects from a CSV, or clear an explicit bind so projects
inherit the tenant’s **default** Scan Profile (`is_default: true`).

Projects attach to a Scan Profile via `Project.spec.scan_profile_uuid` (not the
reverse). Empty UUID inherits the default profile.

| File | Role |
|------|------|
| [`csv_bulk_set_scanprofile.py`](csv_bulk_set_scanprofile.py) | CLI |
| [`example.csv`](example.csv) | Sample input |
| [`requirements.txt`](requirements.txt) | `endorlabs` SDK |

> Replaces an earlier hard-coded `endorctl` UUID loop in this folder. Prefer this
> script for any new rollout.

## Prerequisites

- Python **3.11+** recommended
- Endor Labs credentials with list access to the tenant
- `--apply` additionally requires Project **update** permission (privileged-read /
  admin-read tokens are dry-run only)

## Install

```bash
python3 -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Credentials

Set environment variables (shell or a local `.env` your process loads):

| Variable | Purpose |
|----------|---------|
| `ENDOR_API_CREDENTIALS_KEY` + `ENDOR_API_CREDENTIALS_SECRET` | API key pair |
| **or** `ENDOR_TOKEN` | Bearer token |
| `ENDOR_NAMESPACE` | Optional default for `-n` |

Do not mix API key and bearer token in the same environment.

| Credential type | Dry-run (default) | `--apply` |
|-----------------|-------------------|-----------|
| Tenant API key / SSO with Project **update** | Yes | Yes |
| Privileged-read / admin-read only | Yes | **No** — omit `--apply` |

Always dry-run first and review the result CSV.

## CSV format

Header row required. At least one identifier column per row:

| Column | Purpose |
|--------|---------|
| `project_uuid` | Preferred — exact Project UUID |
| `repo` | `owner/repo` (GitHub-style slug) |
| `project_name` | Full URL or `meta.name` (e.g. `https://github.com/org/repo.git`) |
| `namespace` | Optional hint if UUID lookup needs a child namespace |
| `scan_profile_uuid` | Optional; status is always refreshed from the API |

Aliases accepted: `uuid`, `repository`, `slug`, `url`, `ns`, etc.

See [`example.csv`](example.csv).

## Run

```bash
# Dry-run: next 35 projects not already on the target profile
python csv_bulk_set_scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> \
  -b 35 \
  -n <tenant>

# Apply (requires Project update permission)
python csv_bulk_set_scanprofile.py projects.csv \
  -sp <ScanProfile-uuid-or-name> \
  -b 35 \
  -n <tenant> \
  --apply

# Clear explicit binds → inherit tenant is_default Scan Profile
python csv_bulk_set_scanprofile.py projects.csv \
  --clear \
  -b 35 \
  -n <tenant> \
  --apply
```

On Windows PowerShell, use backticks for line continuation if you split lines.

## Flags

| Flag | Description |
|------|-------------|
| `csv` | Path to the project list |
| `-sp` / `--scan-profile` | Target ScanProfile **UUID** or **name** |
| `--clear` | Clear `scan_profile_uuid` (inherit default). Mutually exclusive with `-sp` |
| `-b` / `--batch` | Max projects to change among rows **not already** on the target (default `35`) |
| `-n` / `--tenant` | Tenant root (default: `ENDOR_NAMESPACE`) |
| `--apply` | Perform updates; omit for dry-run |
| `--workers` | Parallel resolve workers (default `16`) |
| `--results-dir` | Result CSV directory (default: `<csv_dir>/bulk_set_results`) |

### `-sp Default` vs `--clear`

If a Scan Profile is **named** `Default`, `-sp Default` **binds** that profile’s UUID.

`--clear` sets `scan_profile_uuid` to empty so the platform **inherits** whichever
profile has `is_default: true`. Those are different wire states even when the
named profile is also the default.

## Behavior

1. Resolve the target ScanProfile (or clear mode) under the tenant with hierarchy traverse.
2. Resolve each CSV row to a live Project (UUID preferred; otherwise name/URL search).
3. Skip rows already on the target (or already unbound when using `--clear`).
4. Select the first `-b` remaining rows for this run; mark the rest `beyond_batch`.
5. Dry-run prints `would_update`; `--apply` updates only `spec.scan_profile_uuid`.
6. Writes a timestamped result CSV with per-row `action`, `status`, and `error`.

Re-run the same command after each batch: already-updated rows are skipped automatically.

## Result CSV statuses

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
- Changing the tenant’s **default** Scan Profile itself is out of scope — that
  affects every unbound project; do it deliberately in the UI/API.
