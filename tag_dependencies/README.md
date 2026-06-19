# Tag Dependencies in an Endor Labs Project

This script tags dependencies of an Endor Labs project. It reads a text file containing dependency names and versions and applies one or more tags to the matching `DependencyMetadata` records via the Endor Labs API.

## Prerequisites

- Python 3.6+
- An Endor Labs API key + secret with permission to update DependencyMetadata
- The UUID of the project you want to tag dependencies on

## Installation

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the same directory as the script (you can copy `env_template`):

```
API_KEY=<YOUR_KEY>
API_SECRET=<YOUR_SECRET>
ENDOR_NAMESPACE="<YOUR_TENANT_NAMESPACE>"
```

`ENDOR_NAMESPACE` should be the namespace you authenticate against. If the project lives in a child namespace, the script will discover and use it automatically (it traverses sub-namespaces).

## Dependencies File Format

The dependencies file (default: `dependencies.txt`) lists one dependency per line in `name@version` format. A fully documented template is provided at `dependencies_template.txt` — copy it and edit:

```bash
cp dependencies_template.txt dependencies.txt
# then edit dependencies.txt with the packages you want to tag
```

Rules:

- One dependency per line, in `name@version` format.
- Lines starting with `#` and blank lines are ignored.
- The package name is matched case-insensitively against the `package_name` returned by Endor Labs, with the ecosystem prefix (`npm://`, `pypi://`, `mvn://`, etc.) stripped — so just put the bare package name.
- The version, when provided, must match `resolved_version` exactly.
- If you omit `@version`, every version of that package found in the project will be tagged.

Example:

```
# Tag specific versions
lodash@4.17.21
express@4.18.2

# Tag every version of this package found in the project
urllib3
```

If you don't pass `--dependencies-file` and there is no `dependencies.txt` in the working directory (or it contains only comments/blank lines), the script exits with an error before making any API calls.

## Usage

Apply a single tag to dependencies listed in `dependencies.txt`:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky
```

Apply multiple tags (use `--tag` multiple times or pass a comma-separated list):

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky --tag needs-review

python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky,needs-review
```

Use a custom dependencies file:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --dependencies-file my_deps.txt \
  --tag deprecated
```

Tag dependencies for a specific branch context (instead of the project's default/main context):

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --branch refs/heads/feature-branch \
  --tag risky
```

Replace existing tags instead of merging with them:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky \
  --replace-tags
```

Preview what would change without making any updates:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky \
  --dry-run
```

## CLI Reference

| Flag | Required | Description |
| --- | --- | --- |
| `--project_uuid` | yes | UUID of the project whose dependencies should be tagged. |
| `--tag` | yes | Tag to apply. Repeatable; comma-separated values are also accepted. |
| `--dependencies-file` | no | Path to the dependencies file (default: `dependencies.txt`). |
| `--branch` | no | Branch context to operate on. Defaults to the project's main context. |
| `--replace-tags` | no | Replace existing tags instead of merging with them. |
| `--dry-run` | no | Show planned changes without applying them. |
| `--debug` | no | Verbose request logging. |

## How It Works

1. Resolves the project's namespace (traversing sub-namespaces if necessary).
2. Determines whether to query `CONTEXT_TYPE_MAIN` or a specific branch context based on `--branch`.
3. Lists all `DependencyMetadata` records for the project in that context (paginated).
4. Matches each entry from the dependencies file against the project's dependencies by `package_name` (and `resolved_version` when provided).
5. For each match, merges (or replaces) the requested tags with the existing `meta.tags` and PATCHes the `DependencyMetadata` record via:

   ```
   PATCH /v1/namespaces/{namespace}/dependency-metadata
   {
     "request": {"update_mask": "meta.tags"},
     "object": {"uuid": "...", "meta": {"tags": [...]}}
   }
   ```

The script prints a summary at the end including matched, updated, skipped (already up to date), and unmatched entries.
