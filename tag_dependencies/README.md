# Tag Dependencies in an Endor Labs Project

This script tags dependencies of an Endor Labs project by PATCHing the matching `DependencyMetadata` records via the Endor Labs API. You can select the dependencies to tag in two ways (use either or both):

1. **By name@version** — pass a text file of `name@version` entries via `--dependencies-file`.
2. **By package manifest path** — pass a text file of package paths via `--packages-paths-file`. The script finds PackageVersions whose `spec.resolved_dependencies.dependency_files[].path` matches an entry and tags every dependency imported by those packages.

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

If `--dependencies-file` is not supplied, the script auto-uses `./dependencies.txt` when it exists. The script only errors out if neither `--dependencies-file` nor `--packages-paths-file` resolves to a usable file (see [Auto-detection](#auto-detection) below).

## Packages Paths File Format

The packages-paths file lists one glob pattern per line, using the **same syntax as endorctl's `--include-path` / `--exclude-path`** flags (gitignore-style globs). A documented template is provided at `packages_paths_template.txt`:

```bash
cp packages_paths_template.txt packages_paths.txt
# then edit packages_paths.txt with the patterns you want
```

Pattern syntax (mirrors [endorctl scoping scans](https://docs.endorlabs.com/best-practices/scoping-scans/index)):

- `**` matches any number of path segments (recursive). E.g. `src/java/**` matches every file under `src/java`.
- `*` matches anything within a single path segment (no `/`). E.g. `plugins/*/build.gradle`.
- `?` matches a single character.
- A literal path like `plugins/store-smb/build.gradle` is an exact match.

Matching rules:

- Patterns are matched against the project-relative manifest path (`spec.relative_path` on each PackageVersion). Paths must be relative to the project root — no leading `/` is needed.
- For backwards compatibility, absolute paths from `spec.resolved_dependencies.dependency_files[].path` are also accepted as literal patterns.
- Lines starting with `#` and blank lines are ignored.
- Patterns are case-sensitive. Duplicate entries are de-duplicated automatically.

Example:

```
# Every file under these directories (recursive)
src/java/**
plugins/**

# Specific Gradle subproject manifest
server/build.gradle

# Every build.gradle at any depth
**/build.gradle

# Maven POMs anywhere under modules/
modules/**/pom.xml
```

Every dependency whose `spec.importer_data.package_version_uuid` belongs to a matched PackageVersion will be tagged.

If `--packages-paths-file` is not supplied, the script auto-uses `./packages_paths.txt` when it exists.

## Auto-detection

Each selector flag falls back independently to a default file in the current working directory:

| Flag | Default file (when flag is omitted) |
| --- | --- |
| `--dependencies-file` | `./dependencies.txt` |
| `--packages-paths-file` | `./packages_paths.txt` |

So if you put both files in the directory and run `python tag_dependencies.py --project_uuid <uuid> --tag risky`, the script picks up **both** automatically and tags the union of their matches (deduped by dependency UUID). The script only errors out when neither flag is supplied and neither default file exists.

## Usage

Apply a single tag to dependencies listed in `dependencies.txt`:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --tag risky
```

If you omit `--tag`, the tag `test` is applied:

```bash
python tag_dependencies.py --project_uuid <your_project_uuid>
# tags every match with: test
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

Tag every dependency imported by a set of package manifests:

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --packages-paths-file packages_paths.txt \
  --tag monorepo-pkg-a
```

Combine both selectors (the union is tagged, deduped by dependency UUID):

```bash
python tag_dependencies.py \
  --project_uuid <your_project_uuid> \
  --dependencies-file my_deps.txt \
  --packages-paths-file packages_paths.txt \
  --tag risky
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
| `--tag` | no | Tag to apply. Repeatable; comma-separated values are also accepted. Defaults to `test` when omitted. |
| `--dependencies-file` | no* | Path to the name@version dependencies file. Falls back to `./dependencies.txt` when omitted. |
| `--packages-paths-file` | no* | Path to the package manifest paths / glob patterns file. Falls back to `./packages_paths.txt` when omitted. |
| `--branch` | no | Branch context to operate on. Defaults to the project's main context. |
| `--replace-tags` | no | Replace existing tags instead of merging with them. |
| `--dry-run` | no | Show planned changes without applying them. |
| `--debug` | no | Verbose request logging. |

\* At least one of `--dependencies-file` or `--packages-paths-file` must resolve to a file with at least one entry. A `./dependencies.txt` or `./packages_paths.txt` in the current directory satisfies this automatically.

## How It Works

1. Resolves the project's namespace (traversing sub-namespaces if necessary).
2. Determines whether to query `CONTEXT_TYPE_MAIN` or a specific branch context based on `--branch`.
3. If `--packages-paths-file` is provided:
   - Lists all `PackageVersion` records for the project in that context.
   - Selects those whose `spec.relative_path` (or, as a fallback, an absolute `dependency_files[].path`) matches an entry in the file, using endorctl-compatible gitwildmatch globs (`**`, `*`, `?`).
4. Lists all `DependencyMetadata` records for the project in that context (paginated).
5. Builds the set of dependencies to tag, deduped by `uuid`:
   - From `--dependencies-file`: deps whose `package_name` (and optional `resolved_version`) match an entry.
   - From `--packages-paths-file`: deps whose `spec.importer_data.package_version_uuid` belongs to a matched PackageVersion.
6. For each match, merges (or replaces) the requested tags with the existing `meta.tags` and PATCHes the `DependencyMetadata` record via:

   ```
   PATCH /v1/namespaces/{namespace}/dependency-metadata
   {
     "request": {"update_mask": "meta.tags"},
     "object": {"uuid": "...", "meta": {"tags": [...]}}
   }
   ```

The script prints a summary at the end including matched, updated, skipped (already up to date), and unmatched entries — broken out by source (`dependency` file, `package_path` file, or `both`).
