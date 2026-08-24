# Endor Labs SBOM Generator

This repository contains a script for downloading SBOM files in SPDX format from the Endor Labs API and removing test/dev dependencies to produce cleaned SBOMs.

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
   ORGANIZATION_NAME="<YOUR_ORGANIZATION_NAME>"
   PERSON_EMAIL="<YOUR_EMAIL@company.com>"
   ```

   **Note:** `API_KEY`, `API_SECRET`, and `ENDOR_NAMESPACE` are required. `ORGANIZATION_NAME` and `PERSON_EMAIL` are optional and will be added to the cleaned SBOM's creation information if provided.

#### Examples

Download SPDX SBOM and remove test dependencies (auto-detection):
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps
```

Download SPDX SBOM and remove test dependencies (manual list):
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --test-deps-file my_deps.txt
```

Analyze a specific branch context:
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --branch feature-branch --auto-remove-test-deps
```

Combine auto-detection with manual list:
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps --test-deps-file my_test_deps.txt
```

Override organization and person info via command line:
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps --organization "My Company" --person-email "dev@mycompany.com"
```

**Note:** Organization and person info priority:
1. Command line flags (`--organization` / `--person-email`)
2. Environment variables (`ORGANIZATION_NAME` / `PERSON_EMAIL`)
3. Extracted from original SBOM's creation info

Produce a cleaned SBOM that passes the [SPDX Online Tool](https://tools.spdx.org/app/):
```
python remove_test_dependencies.py --project_uuid <your_project_uuid> --auto-remove-test-deps --spdx-online-tool-validation
```

### SPDX Online Tool Validation

The SBOM returned by the Endor Labs API is valid for Endor's own tooling but is
rejected by the strict SPDX 2.3 validator behind <https://tools.spdx.org/app/>.
Passing `--spdx-online-tool-validation` rewrites the **cleaned** SBOM so it
uploads without errors. The original SBOM is never touched.

What it changes:

| Problem in the exported SBOM | What the flag does |
|---|---|
| SPDXIDs keep characters the spec forbids, e.g. `SPDXRef-Package-@babel/runtime-7.23.9` (npm scopes, Maven `group:artifact`, Go module paths) | Rewrites the id to the allowed `[A-Za-z0-9.-]` charset (`SPDXRef-Package-babel-runtime-7.23.9`) and updates every reference to it |
| `downloadLocation` holds a Package URL such as `pkg:npm/%40babel/runtime@7.23.9`, which is not a download location | Moves the purl to `externalRefs` as a `PACKAGE-MANAGER` / `purl` reference — where SPDX expects it — and sets `downloadLocation` to `NOASSERTION` |
| `licenseConcluded` / `licenseDeclared` carry registry free text such as `The Apache Software License, Version 2.0`. This one makes the validator fail while still *parsing* the file | Maps the text onto a real SPDX identifier where the meaning is unambiguous (`Apache-2.0`); anything else becomes a `LicenseRef-` entry with the original wording preserved in `hasExtractedLicensingInfos` |
| A `downloadLocation` URL with no valid host, e.g. `https://deeplay-io/nice-grpc` | Replaced with `NOASSERTION`, original value kept in the package's `sourceInfo` |
| Duplicate SPDXIDs, unknown relationship types, malformed `supplier`, missing `documentNamespace`, empty `creators`, missing DESCRIBES relationship | Deduplicated, reset or filled in as the spec requires |

The flag prints a summary of every category it changed, so nothing is altered silently.

**License list:** to tell a real SPDX identifier from free text, the script uses the
official SPDX license list. It is fetched once from `https://spdx.org/licenses/`
and cached in `.spdx_license_cache.json` next to the script — delete that file to
pick up a newer list. If the fetch fails the script falls back to a built-in set of
common identifiers and says so; licenses outside it become `LicenseRef-` entries,
which is still valid, just less precise.

Verified against 12 real SPDX exports: an npm project went from 777 validator
errors to 0, and a Maven project that previously could not even be parsed now
validates clean.

### Checking an SBOM locally

`validate_spdx.py` runs the same SPDX 2.3 checks as the online tool, so an SBOM can
be confirmed clean without uploading it:

```
python validate_spdx.py <uuid>-original-spdx.json <uuid>-cleaned-spdx.json
```

It groups messages by kind — hundreds of identical errors read as one line — and
exits non-zero if any file fails, so it drops straight into CI. Expect `FAIL` on
the original and `PASS` on the cleaned file; if both pass, the project simply had
none of the problem cases.

Note that a *parse* failure (what free-text licenses cause) surfaces as a single
message rather than one per package, so `1x failed to parse` can stand for
hundreds of bad values.

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

Only the cleaned SBOM is rewritten by `--spdx-online-tool-validation`; the original
is kept exactly as the API returned it so the two can be compared.
