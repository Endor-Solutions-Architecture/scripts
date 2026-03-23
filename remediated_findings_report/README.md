# Remediated Findings Report

Generates a CSV report of remediated vulnerable findings by fetching finding logs from the Endor API within a date range (and optionally filtered by project), then enriching with PackageVersion (Package Location from `spec.relative_path`, Code Owners from `spec.code_owners.owners`) and CVE ID (from description when present, or from the vulnerabilities API when a GHSA ID is in the description). No input CSV is required—all data comes from the Finding Log, Package Version, and Vulnerabilities APIs.

## Data source

Finding logs are fetched via `GET /namespaces/{namespace}/finding-logs` with a filter on `meta.create_time` (start–end date) and optionally `spec.project_uuid`. Only remediated logs (e.g. `spec.operation==OPERATION_DELETE`) are included based on the filter.

## Output CSV columns

Report uses these display headers:

- **Finding Log UUID**
- **Finding UUID**
- **CVE ID** – From description if it contains a CVE ID; otherwise from the vulnerabilities API when a GHSA ID is in the description; otherwise `missing`.
- **Description** – From finding-logs API; `missing` when not available.
- **Criticality**
- **Package/Application**
- **Package Location** – From package_version `spec.relative_path`; **Not Available** when not available or blank.
- **Code Owners** – From package_version `spec.code_owners.owners`; **Not Available** when not available or blank.
- **Introduced At**
- **Resolved At**
- **Days Unresolved**
- **Tags**
- **Category**
- **Ecosystem**
- **Project UUID**
- **Namespace**

## Setup

1. Create a `.env` file (or set environment variables):

   - **Option A – token directly:** set `ENDOR_TOKEN` and `ENDOR_NAMESPACE`.
   - **Option B – API credentials:** set `API_KEY`, `API_SECRET`, and `ENDOR_NAMESPACE` (script will obtain a token via the auth API).

   ```
   ENDOR_NAMESPACE=<your_namespace>
   ENDOR_TOKEN=<your_token>   # optional if API_KEY and API_SECRET are set
   API_KEY=<your_api_key>     # optional if ENDOR_TOKEN is set
   API_SECRET=<your_api_secret>
   ```

2. Install dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

## Usage

```bash
python generate_remediation_report.py --start-date 2026-01-01 --end-date 2026-01-31 --output report.csv
```

Optional:

- `--project-uuid <uuid>` – Restrict to finding logs for a single project.
- `--batch-size N` – Number of package_version UUIDs per list API request (default: 100).

```bash
python generate_remediation_report.py --start-date 2026-01-01 --end-date 2026-01-31 --output report.csv --project-uuid {project-uuid}
python generate_remediation_report.py --start-date 2026-01-01 --end-date 2026-01-31 --output report.csv --batch-size 200
```

Dates must be in `YYYY-MM-DD` format; `--start-date` must be on or before `--end-date`.

## How it works

1. Builds a filter for finding logs: `meta.create_time` within the given date range, `spec.operation==OPERATION_DELETE` (remediated), and optionally `meta.parent_uuid==<project-uuid>` when `--project-uuid` is provided.
2. Calls `GET /namespaces/{namespace}/finding-logs` with that filter; fetches `uuid`, `meta.description`, `spec.finding_parent_uuid`, and other spec fields; paginates through results.
3. Collects unique package_version UUIDs from `spec.finding_parent_uuid`; calls `GET /namespaces/{namespace}/package-versions` with filter `uuid in (...)` in batches and mask `uuid,spec.relative_path,spec.code_owners.owners`; builds maps to **Package Location** and **Code Owners** (shown as **Not Available** when missing or blank).
4. For each description that contains a GHSA ID and no CVE ID, calls `POST /namespaces/oss/queries/vulnerabilities` once per unique GHSA and caches the CVE ID. CVE ID column is filled from description when a CVE is present, else from that cache when a GHSA is present, else `missing`.
5. Writes the output CSV with all columns in the order listed above.

## Running via Claude Code skill

If you use [Claude Code](https://claude.ai/claude-code), you can run this script through the `generate-remediation-report` skill instead of invoking the script manually.

### Prerequisites

- Claude Code installed and running in the `scripts/` directory of this repo.
- `.env` configured as described in [Setup](#setup) above.

### How to invoke

Type the following in the Claude Code chat:

```
/generate-remediation-report for project with uuid <project-uuid> for the month of <Month YYYY> and write the output to <file>.csv
```

Or just type `/generate-remediation-report` and Claude will prompt you for the required parameters interactively.

### What the skill does

1. **Collects parameters** – parses `--start-date`, `--end-date`, `--output`, and optional `--project-uuid` / `--batch-size` from your message, or asks for any that are missing.
2. **Checks environment setup** – verifies that `.env` exists and that a virtual environment is present at `remediated_findings_report/.venv/`. If the venv is missing, Claude creates it and installs dependencies automatically.
3. **Runs the script** – activates the venv and executes `generate_remediation_report.py` with the collected flags.
4. **Reports results** – confirms the output CSV path and the number of rows written, or surfaces any errors with diagnostic guidance.

### Example

```
/generate-remediation-report for project with uuid <project-uuid> for the month of February 2026 and write the output to sample.csv
```

Claude will resolve the dates to `--start-date 2026-02-01 --end-date 2026-02-28`, set up the environment if needed, run the script, and confirm the output.

## No Warranty

This software is provided on an "as is" basis, without warranty of any kind. You are solely responsible for determining whether this software is suitable for your use.
