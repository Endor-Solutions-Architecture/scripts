# Delete Long-Lived Endor Labs API Keys

Detect Endor Labs API keys whose **total lifetime** (`expiration_time - create_time`) exceeds a threshold (default: **90 days**) and optionally delete them.

The script runs in **dry-run mode by default**. Pass `--delete` to actually remove the offending keys.

## What counts as "long-lived"?

A key is flagged when **either** of the following is true:

- Its lifetime (`expiration_time − create_time`) is greater than the threshold (default 90 days), **or**
- It has no expiration set at all (treated as infinite lifetime).

This is *not* the same as "expires in more than 90 days" — a key issued 5 years ago for a 1-year window has a 365-day lifetime and will be flagged regardless of how much time is left on it today.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in API_KEY, API_SECRET, ENDOR_NAMESPACE
```

The API key configured in `.env` needs permission to **read and delete API keys** in every namespace you want this script to manage. Generate one in the Endor Labs UI under **Settings → Access Control → API Keys**.

## Usage

```bash
# Dry-run (default) — list keys whose lifetime exceeds 90 days
python delete_long_lived_api_keys.py

# Different threshold
python delete_long_lived_api_keys.py --days 30

# Override the namespace from the CLI (instead of .env)
python delete_long_lived_api_keys.py --namespace my-tenant

# Actually delete the flagged keys
python delete_long_lived_api_keys.py --delete

# Delete with a stricter threshold
python delete_long_lived_api_keys.py --days 30 --delete

# Pipe the flagged-key list as JSON (e.g. into jq)
python delete_long_lived_api_keys.py --json | jq '.[] | .uuid'
```

### Flags

| Flag | Description |
|------|-------------|
| `--days N` | Lifetime threshold in days (default: 90) |
| `--delete` | **Actually delete** the flagged keys. Without this flag the script only reports. |
| `--namespace NS` | Override the `ENDOR_NAMESPACE` env var. The namespace is traversed recursively. |
| `--json` | After the human-readable report, also dump the flagged keys as JSON. |

## Example output

```
======================================================================
  Endor Labs – Long-Lived API Key DRY-RUN Report
  Generated  : 2026-05-11 20:25 UTC
  Threshold  : lifetime > 90 days
  Mode       : DRY-RUN  (no keys will be deleted; pass --delete to remove)
======================================================================

[FLAGGED] 2 key(s) WOULD BE DELETED:

  - legacy-ci-key  [ops@example.com]  (my-tenant.platform)
    UUID       : 67ab3c12d1e54a8b9c3f0d2e7a8b1c4d
    Created    : 2024-08-01 14:12 UTC
    Expires    : no expiry set
    Lifetime   : no expiration (infinite)
    Owner      : ops@example.com@google

  - terraform-bootstrap  [devops@example.com]  (my-tenant)
    UUID       : 1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f
    Created    : 2025-01-10 09:00 UTC
    Expires    : 2026-07-10 09:00 UTC
    Lifetime   : 546 days
    Owner      : devops@example.com@google

Summary: 2 flagged, 14 compliant.
======================================================================
```

When `--delete` is passed, the same report is printed first, followed by per-key deletion results:

```
Deleting 2 flagged API key(s)...

  [OK]   deleted legacy-ci-key (67ab3c12...) in 'my-tenant.platform'
  [OK]   deleted terraform-bootstrap (1c2d3e4f...) in 'my-tenant'

Deletion summary: 2 deleted, 0 failed.
```

## Safety notes

- **Default is dry-run.** No HTTP `DELETE` calls are made unless `--delete` is explicitly passed.
- **Per-key namespace.** Each key is deleted in the namespace it actually lives in (taken from `tenant_meta.namespace` on the key object), so traversing a parent namespace still routes deletes correctly.
- **Failures are isolated.** If one delete fails, the script continues with the rest and reports a non-zero exit code at the end.
- **Run dry-run first.** Always inspect the dry-run output before passing `--delete`, especially the first time you change `--days` or the namespace.
- **Rotating ≠ deleting.** Deleting an API key immediately invalidates it. Anything currently authenticating with that key will break. Make sure replacement keys are issued and rolled out *before* you delete.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | No offending keys, or `--delete` ran and every deletion succeeded |
| `1`  | Dry-run found offending keys (use this in CI to gate alerts) |
| `2`  | Configuration / authentication / API failure, or one or more deletes failed |
