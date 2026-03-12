# Disable Automated Scans

Bash script that disables automated scan for all projects under a given parent namespace. It discovers all child namespaces, lists projects in each, and sets `processing_status.disable_automated_scan` to `true` on every project.

## Prerequisites

- **Bash** (script uses `set -e` and standard shell features)
- **endorctl** – Endor Labs CLI, available in your PATH or at `~/endorctl`. Must be authenticated for the target namespace(s).
- **jq** – JSON processor for parsing API output.

## Usage

```bash
./disable_automated_scans.sh <namespace>
```

**Example:**

```bash
./disable_automated_scans.sh your-namespace
```

- `<namespace>` – Parent namespace; the script will operate on this namespace and all child namespaces discovered via the API.

Ensure the script is executable (`chmod +x disable_automated_scans.sh`) and that `endorctl` is configured (e.g. auth) for the parent namespace.

## What the script does

1. **Discover namespaces** – Calls `endorctl api list` for `DependencyMetadata` with `--traverse` and group aggregation on `tenant_meta.namespace` to get all distinct namespaces under the parent.
2. **List projects** – For each namespace, lists all projects with `endorctl api list -r Project --list-all` (with a 3600s timeout).
3. **Disable automated scan** – For each project, runs `endorctl api update` with `--field-mask=processing_status.disable_automated_scan` and `--data='{"processing_status":{"disable_automated_scan": true }}'`.

At the end it prints total projects found and how many were successfully updated.

## Notes

- If a project update fails, the script logs "Failed to update project" and continues with the next project; it does not stop.
- Large numbers of namespaces or projects may take a long time; the Project list call uses a 3600s timeout per namespace.
- Ensure you have permission to update projects in all discovered namespaces.
