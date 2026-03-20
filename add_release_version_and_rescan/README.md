# Release branch tracking

Scripts to track a release branch across multiple repos (e.g. microservices): add a version and rescan, then list findings for that ref across those projects.

## Prerequisites

- Python 3.6+
- `endorctl` installed and in PATH
- Authentication configured for `endorctl`

---

## Script 1: Add version and rescan (`main.py`)

Add a repository version (ref-name) to all projects that match a given tag, then trigger a full rescan for each.

### Usage

```bash
python main.py -n <namespace> --tag <tag> --ref-name <ref-name>
```

| Argument       | Required | Description |
|----------------|----------|-------------|
| `-n`, `--namespace` | Yes | Tenant namespace |
| `--tag`        | Yes | Project tag to match (e.g. `my-product`) |
| `--ref-name`   | Yes | Ref/version to add (e.g. `release/1.0.0` or `v1.0.0`) |

### Example

```bash
python main.py -n your-namespace --tag my-product --ref-name release/1.0.0
```

### What it does

1. Lists projects with `endorctl` filtered by `meta.tags matches '<tag>'`.
2. For each project: creates a `RepositoryVersion` for the ref-name, then triggers a full rescan.
3. Prints a summary of how many projects were updated.

---

## Script 2: List findings by ref (`list_findings_by_ref.py`)

List findings for a given ref-name across all projects that match a tag. Use after script 1 once scans have run.

### Usage

```bash
python list_findings_by_ref.py -n <namespace> --tag <tag> --ref-name <ref-name> [--filter EXPR] [--json]
```

| Argument       | Required | Description |
|----------------|----------|-------------|
| `-n`, `--namespace` | Yes | Tenant namespace |
| `--tag`        | Yes | Project tag to match (same as script 1) |
| `--ref-name`   | Yes | Ref/version to query (e.g. `release/1.1.1`) |
| `--filter`     | No  | Optional filter expression for findings. If omitted, uses default: critical/high, reachable (function + dependency), and normal (not test deps). |
| `--json`       | No  | Also print raw API JSON to stdout (CSV is always written) |

### Example

```bash
# Writes CSV + summary to stderr
python list_findings_by_ref.py -n your-namespace --tag my-product --ref-name release/1.1.1

# Same but also print API JSON to stdout (e.g. pipe to jq)
python list_findings_by_ref.py -n your-namespace --tag my-product --ref-name release/1.1.1 --json > findings.json
```

### What it does

1. Lists projects with the given tag (same as script 1).
2. Builds a combined filter: scope (project UUIDs + `context.type==CONTEXT_TYPE_REF` + `context.id==<ref-name>`) **and** either the default criteria or your `--filter` expression.
3. **Default filter** (when `--filter` is not set): critical or high severity, reachable (function and dependency), and normal (not test dependencies).
4. Runs `endorctl api list -r Finding` with that filter, a default **field-mask** (vulnerability raw, dependency, CVSS, remediation, aliases), and `--list-all`.
5. **Writes a CSV file** with a dynamic name: `findings_<tag>_<ref-name>_<YYYYMMDD_HHMMSS>.csv` (unsafe chars in tag/ref replaced by `_`).
6. Prints a short summary and the CSV path to stderr. With `--json`, also prints the full API response to stdout.

### CSV columns

| Column | Source |
|--------|--------|
| `cwe` | `spec.finding_metadata.vulnerability.spec.raw.endor_vulnerability.cwe` |
| `cve_id` | `spec.finding_metadata.vulnerability.spec.raw.endor_vulnerability.cve_id` |
| `aliases` | `spec.finding_metadata.vulnerability.spec.aliases` (comma-joined) |
| `dependency` | `spec.target_dependency_package_name` |
| `project` | Project `meta.name` from the initial project list (resolved by `spec.project_uuid`) |
| `link` | `https://app.endorlabs.com/t/{namespace}/findings/{uuid}` (finding URL in Endor UI) |
| `fix_available` | `spec.proposed_version` |
| `affected_versions` | `spec.target_dependency_version` |
| `epss_score` | `spec.finding_metadata.vulnerability.spec.epss_score.percentile_score` (decimal from API converted to percentage, e.g. 0.34677 → 34.68) |
| `base_cvss` | CVSS v3 score if present, else v4 base score |
| `cvss_version` | `3` or `4` depending on which score is used |
| `remediation` | `spec.remediation` |
| `remediation_action` | `spec.remediation_action` |

---

## Error handling

- Both scripts check that `endorctl` is available before running.
- Script 1: if add-version or rescan fails for a project, the error is printed and the script continues with the next project.
- Script 2: if listing projects or findings fails, the script exits with an error.
