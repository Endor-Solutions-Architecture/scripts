# Endor Labs Dependency Management Scripts

This repository contains Python scripts for working with Endor Labs API to manage dependencies and SBOMs.

## Scripts

1. **`get_new_dependencies.py`** - Get a list of dependencies that are new to a project after a specific date
2. **`remove_test_dependencies.py`** - Download SBOM files in SPDX format and remove test/dev dependencies to produce cleaned SBOMs

### Prerequisites

- Python 3.6+
- Required Python packages: `requests`, `python-dotenv`
- Endor Labs API key and secret

### Installation

1. Installation:
   ```
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the same directory as the scripts with your Endor Labs API credentials and fill these values or copy paste from env_template:
   ```
   API_KEY=<YOUR_KEY>
   API_SECRET=<YOUR_SECRET>
   ENDOR_NAMESPACE="<YOUR_TENANT_NAMESPACE>"
   ORGANIZATION_NAME="<YOUR_ORGANIZATION_NAME>"
   PERSON_EMAIL="<YOUR_EMAIL@company.com>"
   ```

   **Note:** `API_KEY`, `API_SECRET`, and `ENDOR_NAMESPACE` are required. `ORGANIZATION_NAME` and `PERSON_EMAIL` are optional and will be added to the cleaned SBOM's creation information if provided.

---

## get_new_dependencies.py

Get a list of dependencies that are new to a project after a specific date. The script queries DependencyMetadata for the project and filters by creation date at the API level.

### Usage

```bash
python get_new_dependencies.py --project_uuid <uuid> --date <date>
```

### Arguments

- `--project_uuid` (required): The UUID of the project
- `--date` (required): Cutoff date (format: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`). Dependencies created on or after this date will be included.
- `--output` (optional): Output file path. If not specified, prints to stdout.
- `--format` (optional): Output format - `json` (detailed) or `list` (simple package@version list). Default: `json`

### Examples

Get new dependencies after a specific date (prints to stdout):
```bash
python get_new_dependencies.py --project_uuid <your_project_uuid> --date 2024-01-01
```

Save to JSON file:
```bash
python get_new_dependencies.py --project_uuid <your_project_uuid> --date 2024-01-01 --output new_deps.json
```

Simple list format:
```bash
python get_new_dependencies.py --project_uuid <your_project_uuid> --date 2024-01-01 --format list --output new_deps.txt
```

With timestamp:
```bash
python get_new_dependencies.py --project_uuid <your_project_uuid> --date 2024-01-01T00:00:00Z
```

### Output Formats

**JSON format** (default) includes:
- `package_name`: Name of the package
- `resolved_version`: Version of the package
- `created_date`: Creation date of the dependency
- `uuid`: UUID of the dependency metadata
- `name`: Name from metadata

**List format** outputs simple `package@version` format, one per line.

---

## remove_test_dependencies.py

Download SBOM files in SPDX format from the Endor Labs API and remove test/dev dependencies to produce cleaned SBOMs.

### Usage

```bash
python remove_test_dependencies.py --project_uuid <uuid> [options]
```

### Examples

Download SPDX SBOM and remove test dependencies (auto-detection):
```bash
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps
```

Download SPDX SBOM and remove test dependencies (manual list):
```bash
python remove_test_dependencies.py --project_uuid <your_project_uuid> --test-deps-file my_deps.txt
```

Analyze a specific branch context:
```bash
python remove_test_dependencies.py --project_uuid <your_project_uuid> --branch feature-branch --auto-remove-test-deps
```

Combine auto-detection with manual list:
```bash
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps --test-deps-file my_test_deps.txt
```

Override organization and person info via command line:
```bash
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps --organization "My Company" --person-email "dev@mycompany.com"
```

**Note:** Organization and person info priority:
1. Command line flags (`--organization` / `--person-email`)
2. Environment variables (`ORGANIZATION_NAME` / `PERSON_EMAIL`)
3. Extracted from original SBOM's creation info

### Test Dependencies File

The `remove_test_dependencies.py` script uses a text file (default: `test_dependencies.txt`) to specify which dependencies should be removed. The file should contain one dependency name per line. Lines starting with `#` are treated as comments and ignored.

Example `test_dependencies.txt`:
```
# Test and development dependencies
pytest
pytest-cov
coverage
black
flake8
```

The script will remove these packages and their relationships from the generated SBOM, producing a cleaned version without test dependencies.

**Note**: If no `test_dependencies.txt` file is found, the script will download the SBOM but return it unchanged (no dependencies will be removed).

**Output Files**: The script generates two files:
- `{project_uuid}-original-spdx.json` - The original SBOM downloaded from the API
- `{project_uuid}-cleaned-spdx.json` - The SBOM with test dependencies removed
