# Findings Report

Generates a CSV report of security findings by fetching from the Endor Findings API, then enriching with PackageVersion (Package Location from `spec.relative_path`, Code Owners from `spec.code_owners.owners`) and Projects (Project Name from `meta.name`). CVE, CWE, CVSS, and EPSS data comes directly from the Findings API—no separate Vulnerabilities API call is needed. No input CSV is required—all data comes from the Findings, PackageVersion, and Projects APIs.

## Finding categories

The report covers all major finding categories:

| Category | Derived when `spec.finding_categories` contains |
|---|---|
| Container | `FINDING_CATEGORY_CONTAINER` |
| SAST | `FINDING_CATEGORY_SAST` |
| Secrets | `FINDING_CATEGORY_SECRETS` |
| Malware | `FINDING_CATEGORY_MALWARE` |
| License | `FINDING_CATEGORY_LICENSE_RISK` |
| Operational | `FINDING_CATEGORY_OPERATIONAL` |
| Vulnerability | `FINDING_CATEGORY_VULNERABILITY` |

A single finding can carry multiple categories (e.g. a Container finding also has `FINDING_CATEGORY_VULNERABILITY`). The "Category" column shows a single label based on priority (Container > SAST > Secrets > Malware > License > Operational > Vulnerability).

## Data source

Findings are fetched via `GET /namespaces/{namespace}/findings` with a filter on `meta.create_time <= date(end_date)` and optionally `spec.project_uuid`. The filter also includes `context.type==CONTEXT_TYPE_MAIN`.

## Output CSV columns

- **Finding UUID** – Top-level `uuid` of the finding.
- **Category** – Single label: Container, SAST, Secrets, Malware, License, Operational, or Vulnerability.
- **CVE ID** – From `spec.finding_metadata.vulnerability` aliases or `meta.description`; populated for Vulnerability and Container findings.
- **CWE ID** – From SAST `spec.finding_metadata.custom.cwes`, Vulnerability/Container `spec.finding_metadata.vulnerability.spec.database_specific.cwe_ids`, or Malware `spec.finding_metadata.malware.spec.cwe_id`.
- **Description** – From `meta.description`.
- **Criticality** – From `spec.level`, mapped to human-readable (Critical, High, Medium, Low, Info).
- **Remediation** – From `spec.remediation`.
- **Package/Application** – From `spec.target_dependency_package_name` when present; otherwise from `spec.finding_metadata.source_policy_info.finding_name` or `meta.description`.
- **Package Location** – From PackageVersion `spec.relative_path`; **Not Available** when not available or finding parent is not a PackageVersion.
- **Code Owners** – From PackageVersion `spec.code_owners.owners`; **Not Available** when not available.
- **Location File** – From `spec.dependency_file_paths` (comma-separated). Populated for SAST, Secrets, and SCA findings where available.
- **Introduced At** – From `meta.create_time`.
- **Tags** – From `spec.finding_tags` (comma-separated).
- **Ecosystem** – Mapped from the raw API enum to a human-readable name (e.g. `ECOSYSTEM_PYPI` → `Python`, `ECOSYSTEM_NPM` → `JavaScript`). Full mapping:

  | Raw Value | Display |
  |---|---|
  | `ECOSYSTEM_APK` | APK |
  | `ECOSYSTEM_C` | C/C++ |
  | `ECOSYSTEM_CARGO` | Rust |
  | `ECOSYSTEM_COCOAPOD` | CocoaPods |
  | `ECOSYSTEM_DEBIAN` | Debian |
  | `ECOSYSTEM_GEM` | Ruby |
  | `ECOSYSTEM_GO` | Go |
  | `ECOSYSTEM_MAVEN` | Java |
  | `ECOSYSTEM_NPM` | JavaScript |
  | `ECOSYSTEM_NUGET` | .NET |
  | `ECOSYSTEM_PACKAGIST` | PHP |
  | `ECOSYSTEM_PYPI` | Python |
  | `ECOSYSTEM_RPM` | RPM |
  | `ECOSYSTEM_SWIFT` | Swift |

  Unknown values fall back to stripping the `ECOSYSTEM_` prefix and title-casing the remainder.

- **Project UUID** – From `spec.project_uuid`.
- **Project Name** – From Projects API `meta.name`; **Not Available** when not found.
- **Reachability** – Derived from `spec.finding_tags`: `FINDING_TAGS_REACHABLE_FUNCTION` → **Reachable**, `FINDING_TAGS_UNREACHABLE_FUNCTION` → **Unreachable**, `FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION` → **Potentially Reachable**. Only populated for Vulnerability and Container findings; blank for all others.
- **Fixable** – Derived from `spec.finding_tags`: `FINDING_TAGS_FIX_AVAILABLE` → **Yes**, `FINDING_TAGS_UNFIXABLE` → **No**. Blank when neither tag is present.
- **CVSS Score** – From `spec.finding_metadata.vulnerability.spec.cvss_v3_severity.score`. Populated for Vulnerability and Container findings.
- **EPSS Score** – From `spec.finding_metadata.vulnerability.spec.epss_score.probability_score`. Populated for Vulnerability and Container findings.
- **Namespace** – From `tenant_meta.namespace`.

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
python generate_findings_report.py --end-date 2026-01-31 --output report.csv
```

Optional:

- `--project-uuid <uuid>` – Restrict to findings for a single project.
- `--batch-size N` – Number of UUIDs per batch API request for PackageVersions and Projects (default: 100).
- `--split-by-category` – Write separate CSV files per finding category instead of a single combined file. Files are named `{output_base}_{category}.csv` (e.g. `report_vulnerability.csv`, `report_sast.csv`, `report_secrets.csv`, `report_container.csv`, `report_license.csv`, `report_operational.csv`, `report_malware.csv`). Only categories with findings are written.

```bash
python generate_findings_report.py --end-date 2026-01-31 --output report.csv --project-uuid {project-uuid}
python generate_findings_report.py --end-date 2026-01-31 --output report.csv --batch-size 200
python generate_findings_report.py --end-date 2026-01-31 --output report.csv --split-by-category
```

`--end-date` is required and must be in `YYYY-MM-DD` format.

## How it works

1. Builds a filter for findings: `context.type==CONTEXT_TYPE_MAIN` and `meta.create_time <= date(end_date)`, optionally adding `spec.project_uuid==<uuid>`.
2. Calls `GET /namespaces/{namespace}/findings` with that filter and a field mask; paginates through results.
3. Collects unique `meta.parent_uuid` values where `meta.parent_kind=="PackageVersion"`; calls `GET /namespaces/{namespace}/package-versions` in batches to get **Package Location** and **Code Owners** (shown as **Not Available** when missing).
4. Collects unique `spec.project_uuid` values; calls `GET /namespaces/{namespace}/projects` in batches to get **Project Name** (shown as **Not Available** when missing).
5. For each finding, derives the single **Category** label, extracts **CVE ID** and **CWE ID** from embedded metadata (no separate Vulnerabilities API call), extracts **CVSS Score** and **EPSS Score**, and populates **Reachability** only for Vulnerability/Container findings.
6. Writes the output CSV with all columns in the order listed above. When `--split-by-category` is used, writes separate CSV files per category (e.g. `report_vulnerability.csv`, `report_sast.csv`).

## Claude Code Skill

This script ships with a Claude Code skill (`/generate-findings-report`) that lets you run the report interactively without memorizing flags.

### Prerequisites

The skill is available when Claude Code is opened from the `scripts/` directory (where the `.claude/skills/` folder lives). No extra installation is needed.

### How to use

Invoke the skill in Claude Code:

```
/generate-findings-report
```

Claude will:
1. Ask for any required parameters you haven't provided (`--end-date`, `--output`).
2. Check that your `.env` file and virtual environment are set up before running.
3. Execute the script and confirm the output file(s) created.

You can also pass flags directly in the invocation to skip the prompts:

```
/generate-findings-report --end-date 2026-01-31 --output report.csv
/generate-findings-report --end-date 2026-01-31 --output report.csv --split-by-category
```

### Example session

```
User: /generate-findings-report --end-date 2026-03-31 --output q1_findings.csv --split-by-category

Claude: Checking environment…
  ✓ .env found (ENDOR_NAMESPACE=<tenant_namespace>)
  ✓ .venv found

Running:
  python generate_findings_report.py \
    --end-date 2026-03-31 \
    --output q1_findings.csv \
    --split-by-category

Script completed. Files written:
  q1_findings_vulnerability.csv  (1 234 rows)
  q1_findings_sast.csv           (  87 rows)
  q1_findings_secrets.csv        (  12 rows)
  q1_findings_container.csv      ( 340 rows)
  q1_findings_license.csv        (  56 rows)
  q1_findings_operational.csv    (   8 rows)
```

## No Warranty

This software is provided on an "as is" basis, without warranty of any kind. You are solely responsible for determining whether this software is suitable for your use.
