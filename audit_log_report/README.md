# Audit Log Report Generator

A Streamlit application for generating and analyzing audit log reports from Endor's audit system. This tool allows you to extract and visualize user navigation and user action telemetry data.

## Features

- **Two Report Types**:
  - **User Navigation**: Tracks UI telemetry events (page visits, user interactions)
  - **User Actions**: Tracks user action telemetry (feature usage, system interactions)

- **Flexible Filtering**:
  - Date range selection (hours: 1H, 2H, 4H, 6H, 8H, 12H or days: 1D, 2D, 3D, 4D, 5D, 6D, 7D, 15D, 30D)
  - Optional email/group filtering
  - Namespace-specific data extraction

- **Interactive Data Display**:
  - Sortable and filterable data tables
  - Real-time data processing and visualization
  - Export functionality for filtered data

- **Data Export**:
  - CSV export of visible/filtered data
  - Raw JSON data preservation
  - Organized file structure with timestamps

## Prerequisites

- Python 3.7+
- `endorctl` CLI tool installed and configured
- Access to Endor API with appropriate permissions

## Installation

1. Navigate to the audit log report directory:
   ```bash
   cd scripts/audit_log_report
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the Streamlit application**:
   ```bash
   streamlit run main.py
   ```

2. **Configure the report parameters** in the sidebar:
   - **Namespace**: Enter the tenant namespace to analyze
   - **Report Type**: Choose between "User Navigation" or "User Actions"
   - **Date Range**: Select the time period for data collection
   - **Email/Group Filter** (Optional): Enter specific email or group to filter by

3. **Generate the report** by clicking the "Generate Report" button

4. **View and interact with the data**:
   - Browse the processed data in the interactive table
   - Use built-in filtering and sorting capabilities
   - Export filtered data as CSV

## Report Types

### User Navigation (UI Telemetry)
Tracks user interface interactions and page navigation:
- **Columns**: namespace, date, claims, event, value, session_id, user_id, email, domain, browser, os
- **Events**: PAGE_VISIT, user interactions, UI element clicks
- **Data Source**: `internal.endor.ai.endor.v1.UITelemetry`

### User Actions (User Telemetry)
Tracks user actions and feature usage:
- **Columns**: namespace, date, claims, event, value, timestamp, session_id, user_id, email, domain, properties
- **Events**: INSPECTED_CALL_GRAPH, TOGGLE_INCLUDE_CHILD_NAMESPACES, and other user actions
- **Data Source**: `internal.endor.ai.endor.v1.UserTelemetry`

## Data Structure

### Claims Information
The `claims` column contains structured user information extracted from JWT claims:
- `ID`: User ID
- `domain`: User domain
- `email`: User email address
- `firstname`: User's first name
- `lastname`: User's last name
- `nickname`: User's display name
- `user`: Full user identifier
- `issuer`: Token issuer
- `source_type`: Authentication source type

### Generated Files
Each report generates a timestamped directory containing:
```
generated_reports/{namespace}_audit_logs_{timestamp}/
├── data/
│   ├── raw_audit_logs_{report_type}.json
│   └── processed_audit_logs_{report_type}.csv
└── (Streamlit app data)
```

## API Commands

The application uses the following `endorctl` commands:

**With email filter**:
```bash
endorctl api list -r AuditLog -n <namespace> \
  --filter='spec.claims matches ".*<email>.*" and spec.message_kind=="<message_type>" and meta.create_time > date("<timestamp>")' \
  --field-mask='spec.message_kind,spec.claims,spec.payload' \
  --list-all -t 300s --traverse
```

**Without email filter**:
```bash
endorctl api list -r AuditLog -n <namespace> \
  --filter='spec.message_kind=="<message_type>" and meta.create_time > date("<timestamp>")' \
  --field-mask='spec.message_kind,spec.claims,spec.payload' \
  --list-all -t 300s --traverse
```

Where:
- `<namespace>`: The tenant namespace
- `<email>`: The email/group filter (if specified)
- `<message_type>`: Either `internal.endor.ai.endor.v1.UITelemetry` or `internal.endor.ai.endor.v1.UserTelemetry`
- `<timestamp>`: The calculated cutoff timestamp

## Troubleshooting

### Common Issues

1. **endorctl not found**: Ensure `endorctl` is installed and in your PATH
2. **Permission denied**: Verify you have appropriate API access permissions
3. **No data returned**: Check that the namespace exists and contains audit log data for the specified time range
4. **Timeout errors**: Large date ranges may require longer timeout periods

### Debug Information

The application provides detailed debug information including:
- Exact `endorctl` commands being executed
- Response data lengths and structure
- Sample data entries for verification

## Contributing

When modifying this script:
1. Maintain the same data processing structure for consistency
2. Update the README if adding new features
3. Test with both report types and various date ranges
4. Ensure proper error handling for API failures

## License

This script is part of the Endor internal tools collection and is provided as-is with no guarantee or warranty.
