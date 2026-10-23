---
name: export-dependencies
description: Export unique dependencies with scorecard metrics and/or license info for an Endor Labs namespace
argument-hint: "[--namespace my-namespace] [--report-type licenses|scores|full]"
---

Help the user run the `export_dependencies/main.py` script. Follow these steps:

## 1. Determine report type from user intent

Map the user's natural language request to a `--report-type` value before asking any other questions:

| If the user says… | Use |
|---|---|
| "fetch all licenses", "show license info", "what licenses am I using" | `--report-type licenses` |
| "fetch endor scores", "show dependency scores", "scorecard for my dependencies" | `--report-type scores` |
| "fetch all dependencies", "full report", "dependencies with licenses and scores", "export dependencies" (generic) | `--report-type full` (default) |

If the intent is **vague or unclear**, ask before proceeding:

> "What would you like included in the report?
> 1. **Licenses only** — dependency names and their license info
> 2. **Scores only** — dependency names and Endor scorecard scores
> 3. **Full report** — dependency names, scores, and licenses (default)

## 2. Collect parameters

If $ARGUMENTS contains the needed flags, parse them directly. Otherwise ask the user for:

**Required:**
- `--namespace` (or `-n`) — the Endor Labs namespace (or `ENDOR_NAMESPACE` env var)

**Auth (one of two options):**
- Option A — Bearer token: `--token` (or `ENDOR_TOKEN` env var)
- Option B — API credentials: `--api-key` + `--api-secret` (or `ENDOR_API_CREDENTIALS_KEY` + `ENDOR_API_CREDENTIALS_SECRET` env vars)

**Optional:**
- `--workers N` — parallel workers for metric lookups (default: 20; increase for speed, decrease if rate-limited)
- `--debug` — print per-page progress and diagnostic lines during aggregation

## 3. Check environment setup

Before running, verify dependencies are installed:

```bash
cd export_dependencies
pip install -r requirements.txt
```

## 4. Run the script

Run from the `export_dependencies/` directory:

```bash
# Licenses only
python main.py --namespace <namespace> --token "$ENDOR_TOKEN" --report-type licenses

# Scores only
python main.py --namespace <namespace> --token "$ENDOR_TOKEN" --report-type scores

# Full report (default — same as omitting --report-type)
python main.py --namespace <namespace> --token "$ENDOR_TOKEN"

# Using API credentials
python main.py --namespace <namespace> \
  --api-key "$ENDOR_API_CREDENTIALS_KEY" \
  --api-secret "$ENDOR_API_CREDENTIALS_SECRET" \
  --report-type licenses
```

> **Note:** This script can take several minutes for large namespaces. Warn the user before starting.

## 5. Report results

After the script finishes:
- Confirm the output CSV path (printed as the last line by the script).
- State the number of unique dependencies written and which columns were included.
- If it fails, show the exact error and help diagnose: auth failure, namespace not found, rate limits (suggest lowering `--workers`), or network errors.

**Columns by report type:**

| Report type | Columns written |
|---|---|
| `full` (default) | name, package_version_uuid, count, overall_score, SCORE_CATEGORY_POPULARITY, SCORE_CATEGORY_CODE_QUALITY, SCORE_CATEGORY_SECURITY, SCORE_CATEGORY_ACTIVITY, licenses |
| `licenses` | name, count, licenses |
| `scores` | name, package_version_uuid, count, overall_score, SCORE_CATEGORY_POPULARITY, SCORE_CATEGORY_CODE_QUALITY, SCORE_CATEGORY_SECURITY, SCORE_CATEGORY_ACTIVITY |

**Common issues:**
- Blank metric columns: metrics may not be available for those specific package versions — expected for some entries.
- Many "metrics query objects: 0": verify the dependency package version UUIDs correspond to OSS metric entries.
- Intermittent network errors: lower `--workers`; the script has built-in retries with exponential backoff.
- 401/403 mid-run: the script auto-refreshes the token and retries once when using API credentials.
