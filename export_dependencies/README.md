## Export Dependencies Report

Emulates the "Export" function from the Global dependencies page

Generates a CSV of unique dependencies for a namespace, including per-package version metrics (overall score, category scores) and license names. Data is collected from:
- Dependency metadata grouping (unique dependencies and counts)
- Per-package metrics (from the OSS namespace) for scorecard and license info

### Requirements
- Python 3.9+
- Install dependencies:

```bash
python -m pip install -r requirements.txt
```

### Authentication
Provide either a Bearer token or API credentials:
- Token:
  - Flag: `--token`
  - Env: `ENDOR_TOKEN`
- API credentials:
  - Flags: `--api-key`, `--api-secret`
  - Envs: `ENDOR_API_CREDENTIALS_KEY`, `ENDOR_API_CREDENTIALS_SECRET`

Namespace is required:
- Flag: `--namespace` (or `-n`)
- Env: `ENDOR_NAMESPACE`

### Usage

```bash
# Using a token
python main.py --namespace my-namespace --token "$ENDOR_TOKEN"

# Using API credentials
python main.py --namespace my-namespace \
  --api-key "$ENDOR_API_CREDENTIALS_KEY" \
  --api-secret "$ENDOR_API_CREDENTIALS_SECRET"

# With debug logging
python main.py -n my-namespace --token "$ENDOR_TOKEN" --debug

# Increase parallelism (default: 20 workers)
python main.py -n my-namespace --token "$ENDOR_TOKEN" --workers 40
```

Progress is printed on a single updating line (overwritten in place). With `--debug`, additional diagnostic lines appear during unique-dependency aggregation pagination. For example:
```
Aggregating unique dependencies.  This make take a few minutes ...
[debug] dependency-metadata: fetching page 1 ...
[debug] dependency-metadata: page 1 ok; page groups=500, merged unique groups=500
[debug] dependency-metadata: next page token present, continuing ...
[debug] dependency-metadata: fetching page 2 ...
[debug] dependency-metadata: page 2 ok; page groups=480, merged unique groups=980
[debug] dependency-metadata: no next page, aggregation complete
Number of unique dependencies found before de-duplication: 12345   # only with --debug
Number of unique dependencies after de-duplication: 9876 (removed 2469 duplicates)
(1/9876) processing dependency: pypi://urllib3@1.26.20            # single-line progress (in parallel)
...
```

### Output
The script writes a CSV to `generated_reports/unique_dependencies_<namespace>_<timestamp>.csv`.

CSV columns:
- `name`: dependency identifier (e.g., `pypi://urllib3@1.26.20`)
- `package_version_uuid`: representative UUID for that dependency (chosen by highest associated count)
- `count`: total (aggregated) count of occurrences for this dependency across all groups with the same `meta.name`
- `overall_score`: scorecard overall score (if available)
- `SCORE_CATEGORY_POPULARITY`: numeric score for popularity
- `SCORE_CATEGORY_CODE_QUALITY`: numeric score for code quality
- `SCORE_CATEGORY_SECURITY`: numeric score for security
- `SCORE_CATEGORY_ACTIVITY`: numeric score for activity
- `licenses`: concatenated license names separated by `:`

Example row:
```
pypi://urllib3@1.26.20,66d0988469c594feb187c89a,42,6.5,8,5,4,9,BSD-3-Clause:MIT:Apache-2.0
```

### What the script does
1. Lists dependency metadata grouped by `meta.name` and package version UUIDs.
2. Aggregates counts per `meta.name` by summing `aggregation_count.count` across all groups; chooses a representative UUID with the highest associated count (falls back to importer UUID if needed).
3. For each dependency, queries OSS metrics (scorecard, license info) by `meta.parent_uuid`, paginating as needed.
4. Writes a single CSV with combined dependency counts and metrics.

### Timeouts and Pagination
- Each API call uses `Request-Timeout: 1800`.
- Both listing and query endpoints are paginated; the script iterates until all pages are fetched.

### Performance and Parallelism
- Per-dependency metric lookups are parallelized using a thread pool.
- CSV writes are serialized using a file write lock to avoid corruption under concurrency.
- Control parallelism with `--workers` (default: 20). Increase for faster results; reduce if rate limits are encountered.
- Connection reuse and retries: All HTTP calls use a shared session with connection pooling (sized to `--workers`) and exponential backoff retries for transient errors. This reduces repeated DNS lookups and TLS handshakes and helps mitigate intermittent name resolution or connectivity glitches.

### Notes
- Deduplication: If multiple package_version_uuid values exist for a single `meta.name`, the script aggregates counts and retains the UUID with the highest associated count for metric lookups.
- If a dependency lacks a package_version_uuid, metrics are skipped for that entry.
- In some cases, metrics may be available via `spec.importer_data.package_version_uuid`; the script falls back to this UUID if the primary UUID returns no results (only prints the fallback attempt when `--debug` is set).
- Some queries return results in different shapes; the script supports `spec.query_response.list.objects`, `object.spec.query_response.list.objects`, and `list.objects`.
- The progress line is printed in-place and padded to avoid leftover characters when subsequent messages are shorter.
- Authentication resiliency: When using API credentials (not a static token), the script automatically refreshes the token and retries once if a request returns 401/403.

### Troubleshooting
- If metric columns are blank while licenses appear, metrics might not be available for the specific package version or are not present under the expected keys. The script supports both `spec.metric_values.scorecard.score_card` and `spec.metric_values.scorecard` layouts and also checks `spec.analytic.scorecard`.
- If you see many "metrics query objects: 0", verify that the dependency package version UUIDs correspond to OSS metric entries.
- Ensure the `ENDOR_NAMESPACE` is correct and that your token/credentials are valid.
- If you encounter intermittent network errors (e.g., temporary DNS failures), try lowering `--workers` to reduce concurrent connections, or simply re-run; the built-in connection pooling and retries already handle many transient issues.


