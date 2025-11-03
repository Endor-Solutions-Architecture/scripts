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

## Notes

- The script processes projects sequentially to avoid overwhelming the API
- Large tenants with many projects may take significant time to complete
- State files can be manually edited or deleted to control resumption behavior
- Output files are JSON formatted with 2-space indentation for readability

