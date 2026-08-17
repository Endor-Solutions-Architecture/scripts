## Export Secrets Findings Report

Generates a CSV of secret findings for a namespace **and its child namespaces**. Rows include project identifiers, finding metadata, tags, categories, and detected secret locations. Data is collected from:

- A **count** query on the root namespace (`traverse` + `count`) to report total secret findings up front
- **`GET /v1/namespaces/{tenant_meta.namespace}/namespaces`** with **`traverse` + `count`** first (same total as `endorctl -n <ns> api list -r Namespace --traverse --count`), then paginated listing with the same path; pagination follows **`next_page_id`** or **`next_page_token`** from `list.response`. Each page prints `len(list.objects)`.
- **Per-namespace** `GET /namespaces/{ns}/findings` with **`traverse=false`** so each namespace is listed independently (smaller, parallel-friendly requests)
- One lookup per distinct `(tenant namespace, project_uuid)` pair to resolve **project_name**

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

Typical console output:

```
Querying total secret findings count (traverse + count on root namespace) ...
Total secret findings (namespace + child namespaces): 397
Discovering namespaces under 'my-namespace' ...
Will fetch findings per namespace (3): child-a, child-b, my-namespace
Fetching secret findings per namespace with 3 worker(s) ...
Progress: 397/397 findings | namespaces done 3/3 (last: child-b, +120)
Collected 397 secret finding record(s).
Resolving 45 project name(s) with 20 workers ...
completed 45/45
generated_reports/secret_findings_my-namespace_20260428_095314.csv
```

If the API does not return a parseable total from the count response, the script prints a short notice and progress shows `?` instead of the denominator until namespaces finish. With `--debug`, the full count response body is printed when the total cannot be parsed.

### Output
The script writes a CSV to `generated_reports/secret_findings_<namespace>_<timestamp>.csv`.

CSV columns:
- `finding_uuid`: Finding resource UUID
- `project_uuid`: Project UUID from the finding
- `project_name`: Project `meta.name` (resolved via `GET .../namespaces/{tenant}/projects/{uuid}` using `tenant_meta.namespace` from the finding when present)
- `summary`: Finding summary
- `level`: Finding level (e.g. severity)
- `description`: `meta.description`
- `create_time`: `meta.create_time`
- `meta_tags`: `meta.tags` values joined with `;`
- `finding_tags`: `spec.finding_tags` joined with `;`
- `finding_categories`: `spec.finding_categories` joined with `;` (includes `FINDING_CATEGORY_SECRETS` for exported rows)
- `secret_locations`: Values from `spec.finding_metadata.source_policy_info.results[].fields["Secret Location"]`, joined with `; ` when multiple

Example row (fields abbreviated):

```
finding-uuid,project-uuid,my-repo,Summary text,FINDING_LEVEL_HIGH,...,FINDING_CATEGORY_SECRETS,path/to/file:line
```

### What the script does
1. Issues one **findings list** request on the root namespace with `list_parameters.filter` (secrets), `list_parameters.traverse=true`, and `list_parameters.count=true` (no `page_size` or `mask` on this call)—parses the total from `count_response.count`, or from `list.response` fields such as `total_count` / `aggregation_count`, etc.
2. Lists namespaces via `GET /v1/namespaces/{--namespace}/namespaces` with `traverse`. Uses each row’s **`spec.full_name`** (e.g. `scott-learn.testing-cli-integrated`) for findings API calls—**not** short `meta.name`, which causes 403. Falls back to `meta.name` only if `full_name` is missing. Prepends `--namespace` when it is not already in the list. API order is preserved; rows are not deduplicated.
3. For each namespace in that set, paginates findings with **`traverse=false`** and the same secrets filter, using `list_parameters.page_token` until done. Namespace fetches run in a thread pool (`min(--workers, number of namespaces)`).
4. Merges all findings, then resolves project names in parallel (`--workers`) for each distinct `(tenant_meta.namespace, project_uuid)` pair.
5. Writes the CSV.

### Timeouts and Pagination
- Each API call uses `Request-Timeout: 1800`.
- Findings lists use `list.response.next_page_token`. Namespace discovery uses `list.response.next_page_id`.

### Performance and Parallelism
- **Upfront count**: One lightweight request establishes expected volume when the API returns it.
- **Per-namespace listing**: Faster than a single huge traverse of all findings in many setups; namespaces are fetched **in parallel** (bounded by `--workers`).
- Within a single namespace, pages are still sequential (pagination tokens).
- Project name resolution remains parallel across distinct projects.
- Connection reuse and retries: HTTP calls use a shared session with connection pooling (sized to `--workers`) and urllib3 retries for transient errors and 429.

### Notes
- Only findings with **`FINDING_CATEGORY_SECRETS`** in **`spec.finding_categories`** on **`CONTEXT_TYPE_MAIN`** are exported.
- Namespace strings for findings/project calls come from **`spec.full_name`** on each Namespace object (short `meta.name` alone is not a valid API path under the parent tenant). Duplicate rows produce duplicate scans.
- If collected row count differs from the upfront total, the script prints a short note (findings may have changed mid-run, or count vs list semantics may differ slightly).
- If a finding has no `project_uuid`, **project_name** is left blank.
- Authentication resiliency: With API credentials, the script refreshes the token and retries once on 401/403.

### Troubleshooting
- Empty CSV or unexpected counts: Confirm secret scanner results exist under the namespace tree and filters match your data.
- Blank **secret_locations**: Policy result shape may differ; locations are read from `source_policy_info.results` when present.
- Missing upfront total: Run with `--debug` to print the raw count response; the parser may need extending if the API adds another shape for totals.
- Ensure `ENDOR_NAMESPACE` and credentials are correct.
- Rate limits: lower `--workers` or re-run.

