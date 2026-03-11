# Add Release Version and Rescan

Add a repository version (ref-name) to all projects that match a given tag, then trigger a full rescan for each. Use this to track a release branch across multiple repos (e.g. microservices) so you can later query findings for that version.

## Prerequisites

- Python 3.6+
- `endorctl` installed and in PATH
- Authentication configured for `endorctl`

## Usage

```bash
python main.py -n <namespace> --tag <tag> --ref-name <ref-name>
```

### Arguments

| Argument       | Required | Description |
|----------------|----------|-------------|
| `-n`, `--namespace` | Yes | Tenant namespace |
| `--tag`        | Yes | Project tag to match (e.g. `my-product`) |
| `--ref-name`   | Yes | Ref/version to add (e.g. `release/1.0.0` or `v1.0.0`) |

### Example

```bash
# Add version release/1.0.0 to all projects tagged 'my-product' in leonardo-learn and trigger rescan
python main.py -n leonardo-learn --tag my-product --ref-name release/1.0.0
```

## What it does

1. **List projects**  
   Runs:  
   `endorctl -n <namespace> api list -r Project --filter="meta.tags matches '<tag>'" --field-mask="uuid,meta.name"`

2. **For each project**  
   - Logs: `Updating project <meta.name>`  
   - **Add version**  
     Creates a `RepositoryVersion` with the given ref-name so that version is tracked for the project.  
   - On success, logs: `Triggering rescan for project <meta.name>`  
   - **Trigger rescan**  
     Requests a full rescan so the new version gets scanned.

3. **Summary**  
   Prints how many projects were updated and rescans triggered.

## Error handling

- If `endorctl` is missing or list fails, the script exits with an error.
- If add-version or rescan fails for a project, the error is printed and the script continues with the next project.
- Rescan is only triggered when add-version succeeds for that project.
