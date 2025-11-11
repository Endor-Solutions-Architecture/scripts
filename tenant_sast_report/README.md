# Tenant SAST Report

This script generates a comprehensive SAST (Static Application Security Testing) findings report for projects in a given namespace using `endorctl`.

## Features

- Fetches all projects in a namespace (optionally filtered by tags)
- Retrieves SAST findings for each project
- Generates a CSV report with:
  - Project details (UUID, tenant, name, Endor URL)
  - Finding counts (total, critical, high)
  - Language breakdown (dynamic columns for each language found)

## Prerequisites

- Python 3.6 or higher
- `endorctl` installed and available in PATH
- Proper authentication configured for `endorctl`

## Usage

### Basic Usage (All Projects)
```bash
python main.py -n <namespace>
```

### With Project Tags Filter
```bash
python main.py -n <namespace> --project-tags "prod-sast"
```

### With Findings Tags Filter
```bash
python main.py -n <namespace> --findings-tags "security"
```

### With Both Filters
```bash
python main.py -n <namespace> --project-tags "prod-sast" --findings-tags "security"
```

### Examples

```bash
# Generate report for all projects in your-tenant-name namespace
python main.py -n your-tenant-name

# Generate report only for projects tagged with 'prod-sast'
python main.py -n your-tenant-name --project-tags "prod-sast"

# Generate report for all projects but only findings tagged with 'security'
python main.py -n your-tenant-name --findings-tags "security"

# Generate report for prod-sast projects with security findings
python main.py -n your-tenant-name --project-tags "prod-sast" --findings-tags "security"
```

## Output

The script generates a CSV file in the `generated_reports/` directory with the following format:

```
# Without findings tags filter:
tenant_{namespace}_sast_summary_YYYYMMDD_HHMMSS.csv

# With findings tags filter:
tenant_{namespace}_sast_summary_{findings_tags}_YYYYMMDD_HHMMSS.csv
```

### CSV Columns

- `uuid`: Project UUID
- `tenant`: Tenant namespace
- `name`: Project name (usually Git repository URL)
- `endor_url`: Direct link to project in Endor Labs UI
- `total`: Total number of SAST findings
- `critical`: Number of critical findings
- `high`: Number of high severity findings
- `[language]`: Dynamic columns for each programming language found (sorted alphabetically)

### Example Output

```csv
uuid,tenant,name,endor_url,total,critical,high,kotlin,python,javascript,typescript
65e6431403c7d68d4f9e0bf8,your-tenant-name,https://github.com/pelotoncycle/content.git,https://app.endorlabs.com/t/your-tenant-name/projects/65e6431403c7d68d4f9e0bf8,10,5,2,1,1,1,1
```

## How It Works

1. **Project Discovery**: Uses `endorctl` to list all projects in the specified namespace
   - If `--project-tags` is provided, filters projects by the specified tag
   - If not, retrieves all projects

2. **Finding Retrieval**: For each project, queries SAST findings using:
   ```bash
   # Without findings tags filter:
   endorctl -n <namespace> api list -r Finding --filter "spec.project_uuid==<project_uuid> and spec.finding_categories contains FINDING_CATEGORY_SAST and context.type==CONTEXT_TYPE_MAIN" --field-mask="spec.finding_metadata.custom.languages,spec.level" --list-all
   
   # With findings tags filter:
   endorctl -n <namespace> api list -r Finding --filter "spec.project_uuid==<project_uuid> and spec.finding_categories contains FINDING_CATEGORY_SAST and context.type==CONTEXT_TYPE_MAIN and (meta.description matches '<findings-tags>' or meta.tags matches '<findings-tags>')" --field-mask="spec.finding_metadata.custom.languages,spec.level" --list-all
   ```

3. **Data Processing**: 
   - Counts total, critical, and high severity findings
   - Extracts programming languages from finding metadata
   - Aggregates language counts per project

4. **Report Generation**: Creates a CSV with dynamic language columns sorted alphabetically

## Error Handling

- Validates `endorctl` availability before execution
- Handles API errors gracefully
- Continues processing even if individual projects fail
- Provides detailed error messages for troubleshooting

## Requirements

- No external Python packages required (uses only standard library)
- Compatible with Python 3.6+
