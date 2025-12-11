# Tag Findings with Dependency Depth

This script tags vulnerability findings in Endor Labs with their dependency depth. Direct dependencies are tagged with `dependency-depth:0`, first-degree transitive dependencies with `dependency-depth:1`, and so on.

## Purpose

When analyzing vulnerability findings, it's often useful to know how "deep" a vulnerable dependency is in your dependency tree:

- **Direct dependencies** (`dependency-depth:0`) - Dependencies you explicitly declared in your manifest files
- **Transitive dependencies** (`dependency-depth:1`, `2`, etc.) - Dependencies pulled in by your direct dependencies

This information helps prioritize remediation efforts—direct dependencies are typically easier to update than deeply nested transitive dependencies.

## Prerequisites

- Python 3.8 or higher
- Endor Labs API credentials (API Key and Secret) or a valid ENDOR_TOKEN

## Installation

1. Clone this repository and cd into `tag_findings_with_dependency_depth`
2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up authentication (choose one method):

   **Option A: Using API Key and Secret**

   ```bash
   export ENDOR_API_CREDENTIALS_KEY=your_api_key
   export ENDOR_API_CREDENTIALS_SECRET=your_api_secret
   ```

   **Option B: Using a pre-existing token**

   ```bash
   export ENDOR_TOKEN=your_token
   ```

   Alternatively, create a `.env` file:

   ```
   ENDOR_API_CREDENTIALS_KEY=your_api_key
   ENDOR_API_CREDENTIALS_SECRET=your_api_secret
   ```

## Usage

### Test Mode (Recommended First Step)

Always run in test mode first to see what changes would be made:

```bash
# Test mode for a specific project
python main.py --namespace my-namespace --project-uuid <project-uuid> --test

# Test mode for all projects
python main.py --namespace my-namespace --all-projects --test
```

### Apply Changes

Once you've reviewed the test output, run without `--test` to apply changes:

```bash
# Tag findings for a specific project
python main.py --namespace my-namespace --project-uuid <project-uuid>

# Tag findings for all projects in namespace
python main.py --namespace my-namespace --all-projects
```

### Command Line Options

| Option | Required | Description |
|--------|----------|-------------|
| `--namespace` | Yes | Endor Labs namespace to operate on |
| `--project-uuid` | One of these | UUID of a specific project to process |
| `--all-projects` | One of these | Process all projects in the namespace |
| `--test` | No | Preview changes without applying them |
| `--debug` | No | Enable verbose debug output |
| `--timeout` | No | API request timeout in seconds (default: 60) |

## How It Works

1. **Fetch Projects**: Either a specific project or all projects in the namespace
2. **Fetch PackageVersions**: For each project, get PackageVersions with `CONTEXT_TYPE_MAIN`
3. **Pre-fetch Findings**: Fetch all vulnerability findings for the project in one API call
4. **Build Dependency Graph**: Extract the `resolved_dependencies.dependency_graph` from each PackageVersion
5. **Compute Depths**: Using BFS from root dependencies (those not children of any other dependency), compute the minimum depth for each dependency
6. **Tag Findings**: For each finding, determine the correct `dependency-depth:N` tag based on `spec.target_dependency_package_name`

## Idempotency

The script is idempotent:

- If a finding already has the correct `dependency-depth:N` tag, it's skipped
- If a finding has an incorrect depth tag (e.g., `dependency-depth:2` when it should be `dependency-depth:1`), it's replaced
- Multiple depth tags are consolidated to a single correct tag
- Other tags on the finding are preserved

## Output

### Terminal Output

The script provides a summary showing:

- Number of findings processed
- Changes that would be made (test mode) or were made (live mode)
- Findings where depth couldn't be determined (dependency not in graph)
- PackageVersions skipped due to missing dependency graph
- Any errors encountered

Example test mode output:

```
*** TEST MODE - No changes will be made ***

Output will be written to: dependency_depth_tags_20241210_143052_test.csv

Processing project: https://github.com/my-org/my-repo.git
  Found 2 PackageVersion(s) with CONTEXT_TYPE_MAIN
  Found 45 vulnerability finding(s)

================================================================================
TEST MODE - No changes were made
================================================================================

Summary:
  Total findings processed: 45
  Would update: 40
  Already correct (skipped): 3
  Errors: 0
  Depth unknown (dependency not in graph): 2
  PackageVersions skipped (no dependency graph): 0

Complete results written to: dependency_depth_tags_20241210_143052_test.csv
```

### CSV Output

Complete results are written to a timestamped CSV file for further analysis. The filename format is:

- `dependency_depth_tags_YYYYMMDD_HHMMSS_test.csv` (test mode)
- `dependency_depth_tags_YYYYMMDD_HHMMSS_applied.csv` (live mode)

CSV columns:

| Column | Description |
|--------|-------------|
| `finding_uuid` | UUID of the finding |
| `project_uuid` | UUID of the project |
| `project_name` | Name of the project |
| `package_version_uuid` | UUID of the PackageVersion |
| `package_version_name` | Name of the PackageVersion |
| `target_dependency` | The vulnerable dependency purl |
| `depth` | Computed depth (or "unknown") |
| `status` | `would_update`, `updated`, `skipped`, or `error` |
| `change` | Description of what changed |
| `current_tags` | Existing tags (semicolon-separated) |
| `new_tags` | New tags after update (semicolon-separated) |
| `finding_description` | Description of the finding |

## Troubleshooting

### "Depth unknown" Findings

Some findings may show "depth unknown" if the `target_dependency_package_name` doesn't match any entry in the dependency graph. This can happen if:

- The dependency graph wasn't fully resolved
- The purl format differs between the finding and the graph
- The scan data is stale

### PackageVersions Skipped

PackageVersions without a `resolved_dependencies.dependency_graph` are skipped. This typically happens when:

- Dependency resolution failed during scanning
- The package is an unsupported ecosystem for dependency graphs (e.g., ECOSYSTEM_C)

### API Timeout Errors

For namespaces with many projects or findings, you can increase the timeout:

```bash
python main.py --namespace my-namespace --all-projects --timeout 120
```

### Debug Mode

Use `--debug` to see detailed API calls and internal processing:

```bash
python main.py --namespace my-namespace --project-uuid <uuid> --test --debug
```
