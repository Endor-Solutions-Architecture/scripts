# Endor Labs Dependency Export Tool

This repository contains a Python script for exporting all dependencies using the Endor Labs API. The script exports all dependencies from all projects across all accessible namespaces.

### Prerequisites

- Python 3.6+
- Required Python packages: `requests`, `python-dotenv`
- Endor Labs API key and secret

### Installation

1. Installation:
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\\Scripts\\activate`
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the same directory as the script with your Endor Labs API credentials and fill these values or copy paste from env_template:
   ```
   API_KEY=<YOUR_KEY>
   API_SECRET=<YOUR_SECRET>
   ENDOR_NAMESPACE="<YOUR_TENANT_NAMESPACE>"
   ```

## Usage

### Dependency Export (`export_dependencies.py`)

Exports all dependencies from all projects across all accessible namespaces. The script exports only the main context dependencies and outputs results to the terminal, JSON, and CSV formats.

#### Examples

Export all dependencies:
```
python export_dependencies.py
```

#### Output Files

The script generates timestamped output files:
- `all_dependencies_export_YYYYMMDD_HHMMSS.json` - Complete results in JSON format
- `all_dependencies_export_YYYYMMDD_HHMMSS.csv` - Results in CSV format for easy analysis

#### CSV Columns

The CSV file includes the following columns:
- `dependency_name` - Full name of the dependency (e.g., `npm://lodash`)
- `dependency_version` - Resolved version of the dependency
- `dependency_scope` - Scope of the dependency (if applicable)
- `parent_package_version_name` - Parent package version name (if applicable)
- `namespaces` - Comma-separated list of namespaces where the dependency is found
- `project_count` - Number of projects using this dependency
- `project_uuids` - Semicolon-separated list of project UUIDs using this dependency

**Note:** Dependencies are deduplicated based on name and version. If the same dependency is used by multiple projects, all project UUIDs are aggregated into the `project_uuids` column.

#### Features

- **Deduplication**: Automatically removes duplicate dependencies based on name and version, aggregating all projects that use each dependency
- **Cross-namespace export**: Automatically exports from all accessible namespaces using the `--traverse` parameter
- **Main context only**: Focuses on production dependencies (excludes test/dev contexts)
- **Multiple output formats**: Terminal display, JSON, and CSV
- **Detailed results**: Includes project information, dependency scope, and parent package version information

