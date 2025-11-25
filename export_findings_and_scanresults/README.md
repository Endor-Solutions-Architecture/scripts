# Export Findings and Scan Results

This script exports all findings and scan results for all projects across all namespaces in a tenant. It is designed to handle long-running executions and can resume from interruptions.

## Features

- **Cross-namespace traversal**: Automatically discovers and processes all namespaces in the tenant
- **Idempotent execution**: Tracks processed projects and can resume from previous runs
- **Graceful retries**: Implements exponential backoff for retries on transient failures
- **Progress tracking**: State files track which projects have been processed
- **Structured output**: Findings and scan results are exported as separate JSON files per project

## Usage

### Prerequisites

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables (create a `.env` file or export):
   ```bash
   API_KEY=your_api_key
   API_SECRET=your_api_secret
   ENDOR_NAMESPACE=your_primary_namespace
   ```

### Running the Script

#### Basic Usage

Export all data (will resume from previous run if interrupted):
```bash
python main.py
```

#### Force Re-export

To force re-export of all projects (ignore previous progress):
```bash
python main.py --force
```

#### Specific Namespace

To export only a specific namespace:
```bash
python main.py --namespace my-namespace
```

## Output Structure

The script creates the following directory structure:

```
exports/
  <namespace1>/
    findings_<project-uuid1>.json
    scanresults_<project-uuid1>.json
    findings_<project-uuid2>.json
    scanresults_<project-uuid2>.json
    ...
  <namespace2>/
    ...
.state/
  processed_<namespace1>.json
  processed_<namespace2>.json
  ...
```

### File Formats

- **Findings files**: JSON arrays of finding objects filtered by `context.type==CONTEXT_TYPE_MAIN` and `spec.project_uuid`
- **Scan Results files**: JSON arrays of scan result objects filtered by `context.type==CONTEXT_TYPE_MAIN` and `meta.parent_uuid`

### State Files

State files in `.state/` directory track which projects have been processed. This allows the script to resume from interruptions and skip already-processed projects on subsequent runs.

## How It Works

1. **Namespace Discovery**: The script uses the `/namespaces` REST endpoint with `traverse=True` to discover all namespaces in the tenant
2. **Project Iteration**: For each namespace, it fetches all projects using the `/namespaces/{namespace}/projects` endpoint with pagination
3. **Data Export**: For each project:
   - Queries findings using the `/namespaces/{namespace}/findings` REST endpoint with filter `context.type==CONTEXT_TYPE_MAIN and spec.project_uuid==<uuid>` using `page_id` pagination
   - Queries scan results using the `/namespaces/{namespace}/scan-results` REST endpoint with filter `context.type==CONTEXT_TYPE_MAIN and meta.parent_uuid==<uuid>` using `page_id` pagination
   - Exports both to separate JSON files
   - Marks project as processed in state file

## Retry Logic

The script implements exponential backoff retry logic for:
- HTTP 429 (Rate Limiting)
- HTTP 5xx (Server Errors)
- Network timeouts and connection errors

Default settings:
- Maximum 5 retries
- Base delay of 1 second, doubling on each retry

## Performance

The script uses REST API endpoints directly (instead of the query service) for better performance:
- All endpoints support `page_id` pagination for efficient data retrieval
- Each endpoint is called directly, avoiding the overhead of the query service
- The script processes projects sequentially to avoid overwhelming the API

## Indexing Support

The exported data is structured to support efficient queries:
- **Findings**: Indexed by `spec.project_uuid` (project UUID stored in spec)
- **Scan Results**: Indexed by `meta.parent_uuid` (project UUID stored in meta.parent_uuid)

This structure allows for efficient lookup of all findings or scan results for a given project UUID.

## Error Handling

- Network errors and API failures are handled with retries
- Individual project failures don't stop the entire export
- Progress is saved after each project completion
- State files allow resuming from interruptions

## Examples

### Resume After Interruption

If the script is interrupted (Ctrl+C), you can simply rerun it:
```bash
python main.py
```

It will skip already-processed projects and continue from where it left off.

### Re-export Everything

To force re-export of all projects:
```bash
python main.py --force
```

This will ignore state files and reprocess everything.

## Creating Tar Archives

After exporting data, you can create a compressed tar archive of a specific namespace's exports for easy backup or transfer:

### Creating a Tar Archive

To create a tar.gz archive of a namespace folder:

```bash
# From the script directory (where exports/ is located)
cd export_findings_and_scanresults

# Create a compressed tar archive of a namespace
tar -czf <namespace>-exports-$(date +%Y%m%d).tar.gz exports/<namespace>/

# Example:
tar -czf my-namespace-exports-20250115.tar.gz exports/my-namespace/
```

### Extracting/Decompressing a Tar Archive

To extract or decompress a tar archive:

```bash
# Extract the archive (creates the exports/<namespace>/ directory structure)
tar -xzf <namespace>-exports-YYYYMMDD.tar.gz

# Example:
tar -xzf my-namespace-exports-20250115.tar.gz

# Extract to a specific directory
tar -xzf <namespace>-exports-YYYYMMDD.tar.gz -C /path/to/destination/

# View contents without extracting (list files in archive)
tar -tzf <namespace>-exports-YYYYMMDD.tar.gz

# Example:
tar -tzf my-namespace-exports-20250115.tar.gz
```

**Note**: The `-x` flag extracts, `-z` handles gzip compression, and `-f` specifies the filename. The `-C` flag can be used to extract to a different directory.

### Alternative: Include Manifest in Archive

To create an archive that includes the manifest CSV:

```bash
# Create archive including the manifest
tar -czf <namespace>-exports-$(date +%Y%m%d).tar.gz exports/<namespace>/export_manifest.csv exports/<namespace>/*.json

# Or archive the entire namespace folder (which includes the manifest)
tar -czf <namespace>-complete-$(date +%Y%m%d).tar.gz exports/<namespace>/
```

## Sanity Check

After exporting data, you can validate the exports using the `sanity_check.py` script. This script compares the counts in the manifest CSV files with current counts from the Endor API to verify export completeness.

### Features

- **Progress Tracking**: Tracks checked projects in state files, allowing resumption after interruptions
- **Error Handling**: Comprehensive retry logic with exponential backoff for API errors, timeouts, and rate limits
- **Error Logging**: Detailed error logs saved to `.sanity_check_logs/` directory
- **Summary Reports**: JSON summary reports with detailed results for all checked projects
- **Resume Support**: Can resume from previous runs, skipping already-checked projects
- **Progress Indicators**: Shows ETA and progress for long-running checks

### Running Sanity Check

#### Check a Specific Namespace

```bash
python sanity_check.py --namespace my-namespace
```

#### Check with Date Filter

To align counts with when the export was performed (useful if time has passed), use a date filter:

```bash
python sanity_check.py --namespace my-namespace --before-date 2025-01-15
```

#### Check All Namespaces

```bash
python sanity_check.py --all-namespaces

# With date filter
python sanity_check.py --all-namespaces --before-date 2025-01-15
```

#### Resume from Previous Check

If the script was interrupted, you can resume from where it left off:

```bash
python sanity_check.py --namespace my-namespace --resume
```

#### Force Recheck All Projects

To force recheck of all projects (clears state):

```bash
python sanity_check.py --namespace my-namespace --force
```

#### Custom Output File

To specify a custom output file for the summary report:

```bash
python sanity_check.py --namespace my-namespace --output my_report.json
```

### Understanding the Results

The sanity check script:
- Reads manifest CSV files from `exports/<namespace>/export_manifest.csv`
- Queries the API for current counts of findings and scan results per project
- Compares manifest counts with API counts
- Reports matches, mismatches, and differences
- Saves detailed results to a JSON summary report
- Logs errors to `.sanity_check_logs/<namespace>_errors.log`

**Match Criteria:**
- Exact match: Counts are identical
- Close match: Counts are within 5% difference (accounts for timing differences)
- Mismatch: Counts differ by more than 5%

**Date Filtering:**
When using `--before-date`, the script filters API counts to only include records created before the specified date. This helps align counts with when the export was performed, accounting for new records created after the export.

**Error Handling:**
- Automatic retries with exponential backoff for:
  - HTTP 429 (Rate Limiting)
  - HTTP 5xx (Server Errors)
  - Network timeouts
  - Connection errors
- Failed projects are logged but don't stop the entire check
- Progress is saved after each successful check, allowing safe interruption

### Output Files

The script generates several output files:

1. **State Files** (`.sanity_check_state/<namespace>_checked_projects.json`):
   - Tracks which projects have been checked
   - Allows resuming from interruptions
   - Can be cleared with `--force` flag

2. **Error Logs** (`.sanity_check_logs/<namespace>_errors.log`):
   - Detailed error logs for each failed check
   - Includes timestamps, error types, and project information
   - Useful for debugging and tracking issues

3. **Summary Report** (`sanity_check_report.json` by default):
   - Complete JSON report with all check results
   - Includes per-project details, timestamps, and statistics
   - Can be customized with `--output` flag

### Example Output

```
============================================================
Checking namespace: my-namespace
============================================================
  Found 10 projects in manifest
  Using date filter: before 2025-01-15
  Checking 10 project(s) (skipping 0 already checked)
  [1/10] Checking my-project (abc12345...) [ETA: 2.3m]
  [2/10] Checking another-project (def67890...) [ETA: 2.1m]
    Findings: manifest=42, API=42, diff=0 (0.0%)
    ScanResults: manifest=15, API=17, diff=2 (13.3%)

============================================================
SANITY CHECK SUMMARY
============================================================

Total Namespaces Checked: 1
Total Projects: 10
Projects Checked: 10
Matches: 9
Mismatches: 1
Errors: 0

Match Rate: 90.0%

Per-Namespace Results:
  my-namespace: 9/10 matches (90.0%)
    Mismatches:
      another-project:
        ScanResults: 15 vs 17 (diff: 2)

Summary report saved to: sanity_check_report.json

Error logs available in: .sanity_check_logs/
  - my-namespace_errors.log: 1 error(s)
```

### Exit Codes

The script uses different exit codes to indicate results:
- `0`: All checks passed (no mismatches or errors)
- `1`: Mismatches found (count differences > 5%)
- `2`: Errors encountered (API failures, timeouts, etc.)
- `130`: Interrupted by user (Ctrl+C)

## Notes

- The script processes projects concurrently using multiple threads for better performance
- Large tenants with many projects may take significant time to complete
- State files can be manually edited or deleted to control resumption behavior
- Output files are JSON formatted with 2-space indentation for readability
- Use the sanity check script to validate exports before archiving or sharing data

