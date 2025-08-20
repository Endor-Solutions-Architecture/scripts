# Purge On-Premise Queued Scan Jobs

This script automates the purging of on-premise queued scan jobs using the `endorctl` command-line tool. It's specifically designed to address queue cleanup in **Outpost** deployments where Endor Labs monitoring scans are processed on your private Kubernetes cluster infrastructure.

## About Outpost

[Outpost](https://docs.endorlabs.com/deployment/monitoring-scans/outpost/) is Endor Labs' on-premise scheduler for monitoring scans that runs on your private Kubernetes cluster. When using Outpost, all monitoring scans in your Endor Labs tenant are executed within your firewall, and only scan results are sent to the Endor Labs platform.

This script helps manage and clean up queued scan requests that may accumulate in Outpost deployments, particularly useful for:
- **Queue management** in on-premise Kubernetes clusters running Endor Labs monitoring scans
- **Infrastructure cleanup** when scan requests get stuck or need manual intervention

## Prerequisites

- `endorctl` must be installed and available in your PATH
- Proper authentication and permissions to access the Endor API
- Python 3.6+ (uses standard library modules only)

## Usage

```bash
python main.py -n <namespace> --persist <true|false>
```

### Parameters

- **-n, --namespace**: The namespace/tenant to process (e.g., "avalara.global-ui")
- **--persist**: Either "true" or "false"
  - `false`: Dry run mode - generates CSV but doesn't delete anything
  - `true`: Actually deletes the scan requests

### Examples

**Dry run (safe mode):**
```bash
python main.py -n "avalara.global-ui" --persist false
```

**Actual deletion:**
```bash
python main.py -n "avalara.global-ui" --persist true
```

**Alternative long form:**
```bash
python main.py --namespace "avalara.global-ui" --persist true
```

## What the Script Does

1. **Counts queued scans**: First runs a count command to see how many scan requests exist
2. **Retrieves scan details**: Gets the full list with required fields (UUID, namespace, project_uuid, installation_uuid)
3. **Processes each request**: 
   - If `persist=false`: Logs information and marks all as not deleted
   - If `persist=true`: Attempts to delete each scan request and logs success/failure
4. **Generates CSV report**: Creates a timestamped CSV file with results

## Why This Script is Needed for Outpost Deployments

In Outpost deployments, scan requests are processed on your private Kubernetes cluster. Sometimes these requests can get stuck in a queued state due to:
- Resource constraints on your cluster
- Configuration changes that affect scan processing
- Cluster scaling or maintenance events

This script provides a way to:
- **Audit** what scan requests are currently queued
- **Clean up** stuck or unnecessary scan requests
- **Maintain** your on-premise scanning infrastructure

## Output

### Console Output
The script provides detailed logging of:
- Count of found scan requests
- Processing status for each request
- Success/failure of deletions (if persist=true)
- Summary statistics

### CSV File
Generates a file named: `purge_scans_tenant_<namespace>_<timestamp>.csv` in the `generated_reports/` folder

Columns:
- `scan_request_id`: The UUID of the scan request
- `namespace`: The tenant namespace
- `project_uuid`: Project UUID (if applicable)
- `installation_uuid`: Installation UUID (if applicable)
- `deleted`: Boolean indicating if deletion was successful (true/false)

## Error Handling

- If `endorctl` is not available, the script exits with an error
- If no queued scans are found, the script exits cleanly
- If individual deletions fail, the script continues processing other requests
- All errors are logged to the console for debugging

## Safety Features

- **Dry run mode**: Use `persist=false` to safely see what would be deleted
- **Count check**: Script exits if no scan requests are found
- **Individual error handling**: One failed deletion doesn't stop the entire process
- **Detailed logging**: Full visibility into what's happening at each step

## Scan Request Types Targeted

This script specifically targets scan requests that meet these criteria:
- **Status**: `SCAN_REQUEST_STATUS_QUEUED` - Requests waiting to be processed
- **Type**: `SCAN_REQUEST_TYPE_SCHEDULED` - Regularly scheduled monitoring scans
- **Location**: `is_on_premise=true` - Scans running on your Outpost infrastructure

These are typically the monitoring scans that Endor Labs Apps initiate every 24 hours to continuously monitor your repositories for vulnerabilities and code weaknesses.

## Example Output

```
Starting scan request purge process
Tenant: avalara.global-ui
Persist mode: true
--------------------------------------------------
Counting queued on-premise scan requests in namespace: avalara.global-ui
Found 25 queued on-premise scan requests
Retrieving queued on-premise scan requests from namespace: avalara.global-ui
Retrieved 25 scan request objects
Deleting Scan Request with Id 68a24c593861cb0b9bf36c19 from namespace avalara.global-ui, installation_uuid: 6895a498c1bced1da4975757
  Success: true
...

Results written to: purge_scans_tenant_avalara.global-ui_20241201_143022.csv

Summary:
  Total scan requests processed: 25
  Total scan requests deleted: 25
  Total scan requests failed to delete: 0

Scan request purge process completed successfully!
```
