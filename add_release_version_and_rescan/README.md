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
python main.py -n leonardo-learn --tag my-product --ref-name release/1.0.0
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
python list_findings_by_ref.py -n <namespace> --tag <tag> --ref-name <ref-name> [--json]
```

| Argument       | Required | Description |
|----------------|----------|-------------|
| `-n`, `--namespace` | Yes | Tenant namespace |
| `--tag`        | Yes | Project tag to match (same as script 1) |
| `--ref-name`   | Yes | Ref/version to query (e.g. `release/1.1.1`) |
| `--json`       | No  | Print only raw JSON to stdout (no summary) |

### Example

```bash
# Summary + full JSON
python list_findings_by_ref.py -n leonardo-learn --tag my-product --ref-name release/1.1.1

# Only JSON (e.g. pipe to jq or save to file)
python list_findings_by_ref.py -n leonardo-learn --tag my-product --ref-name release/1.1.1 --json > findings.json
```

### What it does

1. Lists projects with the given tag (same as script 1).
2. Runs:  
   `endorctl -n <namespace> api list -r Finding --filter="spec.project_uuid in ['uuid1','uuid2',...] and context.type=='CONTEXT_TYPE_REF' and context.id=='<ref-name>'" --list-all`
3. Prints a short summary to stderr and the full API response JSON to stdout.

---

## Error handling

- Both scripts check that `endorctl` is available before running.
- Script 1: if add-version or rescan fails for a project, the error is printed and the script continues with the next project.
- Script 2: if listing projects or findings fails, the script exits with an error.
