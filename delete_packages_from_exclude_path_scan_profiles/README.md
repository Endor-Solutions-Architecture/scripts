## Delete Package Versions Matching Scan Profile `excluded_paths`

This script walks every `ScanProfile` in your Endor Labs namespace tree (with `traverse=True`), reads each profile's `spec.automated_scan_parameters.excluded_paths`, finds the projects that profile governs, and queries the `PackageVersion`s in those projects whose `spec.relative_path` matches any of the configured exclude-path globs.

It then either **lists** them (dry run, default) or **deletes** them (`--no-dry-run`).

### How a scan profile's scope is determined

For each scan profile found in the namespace tree, the script picks the projects to consider as follows:

- **Default profile** (`spec.is_default == true`): all projects in the profile's namespace tree whose `spec.scan_profile_uuid` is empty (i.e. they fall back to the namespace default).
- **Scoped profile** (non-default): all projects whose `spec.scan_profile_uuid == <profile.uuid>`.

Only `CONTEXT_TYPE_MAIN` package versions are considered, and a package is deduplicated across profiles before deletion.

### Glob conversion

Endor scan profile exclude paths are gitignore-style globs (e.g. `**/*Test/**`, `src/tests/**`, `**/*.NUnit/**`). The script converts each glob to an anchored, case-insensitive Go/RE2 regex and combines them via alternation, then passes that to the `spec.relative_path matches '<regex>'` filter on the `PackageVersion` query.

| Glob fragment | Regex |
| --- | --- |
| `**/`         | `(?:.*/)?` |
| `**`          | `.*`        |
| `*`           | `[^/]*`     |
| `?`           | `[^/]`      |

The combined filter sent to Endor for each profile looks like:

```
context.type==CONTEXT_TYPE_MAIN
  and (spec.project_uuid=="<id1>" or spec.project_uuid=="<id2>" ...)
  and spec.relative_path matches '(?i)^(?:<glob1-regex>|<glob2-regex>|...)$'
```

Project UUIDs are batched (50 per request) to keep filter strings small.

## SETUP

Step 1: Create a `.env` file in the same directory as the script. The API key needs permission to read `ScanProfile`, `Project`, and `PackageVersion`, plus delete `PackageVersion`.

```
API_KEY=<your_api_key_here>
API_SECRET=<your_api_secret_here>
ENDOR_NAMESPACE=<your_namespace>
```

Step 2: Set up a Python virtual environment and install dependencies.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Step 3: Run the script.

*   **Dry run (default):** list all packages that would be deleted.

    ```bash
    python3 main.py
    ```

*   **Delete:** actually delete every matching package version.

    ```bash
    python3 main.py --no-dry-run
    ```

*   **Restrict to a single scan profile:** useful while iterating.

    ```bash
    python3 main.py --scan-profile-uuid <profile-uuid>
    ```

**Caution:** deletion is permanent. Always review a dry-run first.

## No Warranty

Please be advised that this software is provided on an "as is" basis, without warranty of any kind, express or implied. The authors and contributors make no representations or warranties of any kind concerning the safety, suitability, lack of viruses, inaccuracies, typographical errors, or other harmful components of this software. There are inherent dangers in the use of any software, and you are solely responsible for determining whether this software is compatible with your equipment and other software installed on your equipment.

By using this software, you acknowledge that you have read this disclaimer, understand it, and agree to be bound by its terms and conditions. You also agree that the authors and contributors of this software are not liable for any damages you may suffer as a result of using, modifying, or distributing this software.
