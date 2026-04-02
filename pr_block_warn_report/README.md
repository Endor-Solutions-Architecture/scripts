# PR Block/Warn Report

Generates a report of PR scans that triggered action policy enforcement (block or warn) across a namespace. The report links `ScanRequest` metadata with `ScanResult` to determine the enforcement outcome using `blocking_findings` and `warning_findings` fields.

There are two ways to use this tool:

1. **CLI** (`main.py`) — generates a CSV report directly
2. **Dashboard** (`dashboard.py`) — interactive Streamlit app with filters, timeline charts, and CSV export

## Prerequisites

- `endorctl` installed and available in your PATH
- Authenticated to the target namespace
- Python 3.8+

## CLI Usage

```bash
pip install -r requirements.txt  # only needed for dashboard
python main.py -n <namespace> [--days 30]
```

### Parameters

- **-n, --namespace** (required): Namespace/tenant to query
- **--days** (optional): Number of days to look back (default: 30)

### Example

```bash
python main.py -n "acme-corp" --days 14
```

Output is written to `generated_reports/pr_block_warn_<namespace>_<timestamp>.csv`.

## Dashboard Usage

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

The dashboard provides:

- **Summary metrics**: total block/warn PRs, breakdown by outcome, projects affected
- **Filters**: by project, outcome (block/warn), and free-text search
- **Timeline chart**: daily block/warn counts over time
- **Top projects**: ranked by enforcement frequency
- **Data table**: full details with clickable project and PR links
- **CSV export**: download filtered results

## How It Works

1. Queries `ScanRequest` objects that completed successfully with a `ci_run_uuid`
2. For each scan, fetches the linked `ScanResult` via `spec.environment.config.ExecutionID`
3. Classifies outcome from `ScanResult`:
   - `spec.blocking_findings` non-empty → **block**
   - `spec.warning_findings` non-empty → **warn**
4. Resolves project UUIDs to repository names
5. Outputs results ordered by date (most recent first)

The linkage between models is:
- `ScanRequest.spec.result.ci_run_uuid` → `ScanResult.spec.environment.config.ExecutionID`

## Output Columns

| Column | Description |
|---|---|
| date | When the PR scan was scheduled |
| project_name | Repository full name (e.g., `org/repo`) |
| project_url | Link to project in Endor Labs UI |
| pr_url | Link to the pull request |
| outcome | `block` or `warn` |
| blocker_findings | Count of blocking findings from ScanResult |
| warning_findings | Count of warning findings from ScanResult |
| exit_code | Exit code from the scan result |
| policies_triggered | Action policies that were triggered |
| pr_check_conclusion | PR check run conclusion from the scan request |
| ci_run_uuid | CI run UUID linking ScanRequest to ScanResult |

## Notes

- The script makes one `ScanResult` query per PR scan. For namespaces with many PR scans, the CLI run may take several minutes.
- Only PR scans where the linked `ScanResult` has at least one blocking or warning finding are included.
- `ScanResult` is the primary source of truth for block/warn classification. `Finding` tags (`FINDING_TAGS_CI_BLOCKER`, `FINDING_TAGS_CI_WARNING`) can be used as a fallback if `ScanResult` linkage is incomplete.
