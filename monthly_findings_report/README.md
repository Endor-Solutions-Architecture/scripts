# Monthly Findings Report

Generates a consolidated CSV report of all vulnerability findings relevant to a given month. Combines **active (open)** findings from the Findings API with **remediated (fixed)** findings from the Finding Logs API.

## What's included

| Scenario | Status | Source |
|----------|--------|--------|
| Created in month, still open | Open | Findings API |
| Created in month, fixed in same month | Fixed | Finding Logs API |
| Created before month, fixed during month | Fixed | Finding Logs API |

## Setup

```bash
cd monthly_findings_report
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your credentials
```

## Usage

```bash
# Default: previous calendar month
python monthly_findings_report.py --output march_2026.csv

# Explicit date range
python monthly_findings_report.py \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --output march_2026.csv

# Filter to a single project
python monthly_findings_report.py \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --project-uuid <uuid> \
  --output march_2026.csv
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--output` | Yes | — | Output CSV file path |
| `--start-date` | No | First day of previous month | Report start (YYYY-MM-DD) |
| `--end-date` | No | Last day of previous month | Report end (YYYY-MM-DD) |
| `--project-uuid` | No | All projects | Filter to a single project |
| `--batch-size` | No | 100 | Package version UUIDs per API request |

## Output columns

| Column | Description |
|--------|-------------|
| Finding UUID | Unique identifier for the finding |
| CVE ID | CVE or GHSA identifier |
| Description | Finding description |
| Criticality | Severity level (Critical, High, Medium, Low) |
| **Status** | **Open** or **Fixed** |
| Package/Application | Affected package name |
| Package Location | Relative path in the repository |
| Code Owners | Code owners for the package |
| **Created At** | When the finding was first introduced |
| **Resolved At** | When the finding was fixed (blank if Open) |
| Days Unresolved | Number of days the finding was open |
| Tags | Finding tags |
| Category | Finding category |
| Ecosystem | Language ecosystem (Java, Python, etc.) |
| Project UUID | Project identifier |
| Reachability | Reachable / Unreachable / Potentially Reachable |
| Fixable | Yes / No |
| Namespace | Endor Labs namespace |

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENDOR_NAMESPACE` | Yes | Your Endor Labs namespace |
| `ENDOR_API_TOKEN` | One of | Direct bearer token |
| `API_KEY` + `API_SECRET` | One of | API key authentication |

## Data sources

- **Open findings**: `GET /v1/namespaces/{ns}/findings` — active vulnerability findings created within the date range, excluding dismissed exceptions
- **Fixed findings**: `GET /v1/namespaces/{ns}/finding-logs` — finding logs with `OPERATION_DELETE` (remediation) within the date range
