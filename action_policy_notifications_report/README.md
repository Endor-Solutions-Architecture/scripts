# Action Policy Notifications Report

This script generates comprehensive CSV reports for notification policies using the `endorctl` command-line tool. It's specifically designed to evaluate notification policies that integrate with JIRA, providing detailed insights into JIRA ticket creation, updates, and resolution status. The script retrieves all notifications associated with a specific policy and provides comprehensive information about JIRA integration effectiveness, project details, and error tracking.

## Prerequisites

- `endorctl` must be installed and available in your PATH
- Proper authentication and permissions to access the Endor Labs API
- Python 3.6+ (uses standard library modules only)

## Usage

```bash
python main.py -n <namespace> --policy-uuid <policy-uuid>
```

### Parameters

- **-n, --namespace**: The namespace/tenant to process (e.g., "namespace.global-ui")
- **--policy-uuid**: The UUID of the notification policy to generate a report for

### Examples

**Generate report for a specific policy:**
```bash
python main.py -n "namespace.global-ui" --policy-uuid "66bce54b365cdbc3f135a32f"
```

**Alternative long form:**
```bash
python main.py --namespace "namespace.global-ui" --policy-uuid "66bce54b365cdbc3f135a32f"
```

## What the Script Does

1. **Validates Policy**: 
   - Retrieves policy details using the provided UUID
   - Verifies the policy exists and is of type `POLICY_TYPE_NOTIFICATION`
   - Exits with error if policy is not found or is not a notification policy

2. **Retrieves Notifications**: 
   - Fetches all notifications associated with the policy
   - Includes notification metadata, project information, and action data

3. **Enriches Project Data**: 
   - Retrieves project names for all projects referenced in notifications
   - Maps project UUIDs to human-readable names

4. **Processes Action Data**: 
   - Extracts JIRA integration information (issue keys, action completion status)
   - Aggregates error information from all notification actions
   - Handles missing data gracefully

5. **Generates CSV Report**: 
   - Creates a comprehensive CSV file with all notification details
   - Includes direct links to notifications and projects in the Endor Labs UI

## Output

### Console Output
The script provides detailed logging of:
- Policy validation results
- Number of notifications retrieved
- Project name resolution progress
- Report generation status

### CSV File
Generates a file named: `policy_{uuid}_{policy_name}_{timestamp}.csv` in the `generated_reports/` folder

Columns:
- **notification_uuid**: The UUID of the notification
- **notification_link**: Direct link to view the notification in Endor Labs UI (routes to open or resolved based on state)
- **project_uuid**: Project UUID
- **project_name**: Human-readable project name
- **project_url**: Direct link to the project in Endor Labs UI
- **branch**: Git branch context (e.g., "master")
- **state**: Notification state (e.g., "NOTIFICATION_STATE_OPEN")
- **jira_id**: JIRA issue key if JIRA integration is active
- **was_created**: Boolean indicating if JIRA ticket was created
- **was_updated**: Boolean indicating if JIRA ticket was updated
- **was_resolved**: Boolean indicating if JIRA ticket was resolved
- **errors**: Aggregated error messages from all notification actions (pipe-separated)

## JIRA Integration Details

The script specifically looks for JIRA integration data in the `notification_action_data` field:
- Searches for actions with `notification_target_type: "ACTION_TYPE_JIRA"`
- Extracts JIRA issue keys from `metadata.data.issue_key`
- Tracks completion status of create, update, and resolve actions
- Handles cases where JIRA data may be missing (e.g., when `open_action_complete` is false)

## Error Handling

- **Policy Validation**: Exits gracefully if policy is not found or wrong type
- **Missing Data**: Handles missing JIRA metadata gracefully
- **API Errors**: Continues processing even if some API calls fail
- **File Operations**: Creates output directory if it doesn't exist

## Example Output

```
Starting notification report generation
Namespace: namespace.global-ui
Policy UUID: 66bce54b365cdbc3f135a32f
--------------------------------------------------
Retrieving policy details for UUID: 66bce54b365cdbc3f135a32f
Found policy: SCA - Critical Findings
Policy type: POLICY_TYPE_NOTIFICATION
Retrieving notifications for policy: 66bce54b365cdbc3f135a32f
Retrieved 25 notifications
Retrieving project names for 15 projects

Report generated successfully: generated_reports/policy_66bce54b365cdbc3f135a32f_SCA_-_Critical_Findings_20241201_143022.csv
Total notifications processed: 25

Notification report generation completed successfully!
```

## Use Cases

This script is particularly useful for:
- **JIRA integration evaluation**: Assess the effectiveness of JIRA integration for notification policies
- **JIRA ticket tracking**: Monitor which notifications successfully created, updated, or resolved JIRA tickets
- **Integration troubleshooting**: Identify and resolve JIRA integration failures and errors
- **Policy effectiveness analysis**: Evaluate how well notification policies are working with JIRA workflows
