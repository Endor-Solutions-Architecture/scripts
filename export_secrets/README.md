## Export Secrets Findings Report

Generates a CSV of secret findings for a namespace. Rows include project identifiers, finding metadata, tags, categories, and detected secret locations. Data is collected from:

- The Findings list API (`GET /namespaces/{namespace}/findings`), filtered to main-branch secrets via `spec.finding_categories`
- One lookup per distinct project UUID to resolve `meta.name` for the **project_name** column

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

After findings are loaded, if there are distinct projects, progress for project name resolution prints on a single updating line (`completed N/M`). Pagination detail for the findings list appears only with `--debug`:

```
Listing secret findings (FINDING_CATEGORY_SECRETS). This may take a few minutes ...
[debug] findings (secrets): fetching page 1 ...
[debug] findings (secrets): page 1 ok; batch=500, total=500
[debug] findings (secrets): fetching page 2 ...
Found 1200 secret findings.
Resolving 45 project name(s) with 20 workers ...
completed 45/45
generated_reports/secret_findings_my-namespace_20260428_095314.csv
```

### Output
The script writes a CSV to `generated_reports/secret_findings_<namespace>_<timestamp>.csv`.

CSV columns:
- `finding_uuid`: Finding resource UUID
- `project_uuid`: Project UUID from the finding
- `project_name`: Project `meta.name` (resolved via the Projects API)
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
1. Lists all findings matching `context.type==CONTEXT_TYPE_MAIN` and `spec.finding_categories contains ['FINDING_CATEGORY_SECRETS']`, with traverse and a field mask for UUID, meta, and spec fields needed for the CSV.
2. Paginates with `list_parameters.page_token` until all pages are retrieved.
3. Collects distinct `spec.project_uuid` values and fetches each project’s name in parallel (thread pool).
4. Writes one CSV row per finding, single-threaded after lookups complete.

### Timeouts and Pagination
- Each API call uses `Request-Timeout: 1800`.
- The findings list is paginated; the script follows `list.response.next_page_token` until exhausted.

### Performance and Parallelism
- Finding list pagination runs sequentially (each page depends on the prior page token).
- Project name resolution runs in parallel: `--workers` controls the thread pool size for `GET .../projects/{uuid}` (default: 20). Increase for faster resolution when there are many distinct projects; reduce if rate limits are encountered.
- Connection reuse and retries: HTTP calls use a shared session with connection pooling (sized to `--workers`) and urllib3 retries for transient server errors and rate limiting (429), consistent with the export_dependencies script pattern.

### Notes
- Only findings tagged as secrets via **`FINDING_CATEGORY_SECRETS`** in **`spec.finding_categories`** are exported (main context only).
- If a finding has no `project_uuid`, **project_name** is left blank for that row.
- Authentication resiliency: When using API credentials (not a static token), the script refreshes the token and retries once on 401/403 on individual requests.
- With `--debug`, failed project lookups print a short error line; the CSV still gets an empty **project_name** for that UUID.

### Troubleshooting
- Empty CSV or unexpected counts: Confirm the namespace has secret scanner results and that findings are on **`CONTEXT_TYPE_MAIN`** with **`FINDING_CATEGORY_SECRETS`**.
- Blank **secret_locations**: Policy result shape may differ; locations are read from `source_policy_info.results` when present.
- Ensure `ENDOR_NAMESPACE` and credentials are correct.
- Intermittent network issues: lower `--workers` or re-run; retries and connection pooling cover many transient failures.

