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

The online tool reports two separate results, and the flag is enough for both:

- **SPDX 2.3 validation** — is the document well formed and spec legal.
- **NTIA minimum elements conformance** — does it carry the seven required
  elements (supplier, component name, version, unique identifier, dependency
  relationship, SBOM author, timestamp).

The two are not independent: the conformance checker only calls a document
conformant if it is *also* SPDX valid. The raw Endor export already carries all
seven elements, but its 777 validation errors block conformance outright — so
fixing validity is what makes conformance pass.

What it changes:

| Problem in the exported SBOM | What the flag does |
|---|---|
| SPDXIDs keep characters the spec forbids, e.g. `SPDXRef-Package-@babel/runtime-7.23.9` (npm scopes, Maven `group:artifact`, Go module paths) | Rewrites the id to the allowed `[A-Za-z0-9.-]` charset (`SPDXRef-Package-babel-runtime-7.23.9`) and updates every reference to it |
| `downloadLocation` holds a Package URL such as `pkg:npm/%40babel/runtime@7.23.9`, which is not a download location | Moves the purl to `externalRefs` as a `PACKAGE-MANAGER` / `purl` reference — where SPDX expects it — then sets `downloadLocation` to the package's repository URL if one is available (see below), otherwise `NOASSERTION` |
| `licenseConcluded` / `licenseDeclared` carry registry free text such as `The Apache Software License, Version 2.0`. This one makes the validator fail while still *parsing* the file | Maps the text onto a real SPDX identifier where the meaning is unambiguous (`Apache-2.0`); anything else becomes a `LicenseRef-` entry with the original wording preserved in `hasExtractedLicensingInfos` |
| A `downloadLocation` URL with no valid host, e.g. `https://deeplay-io/nice-grpc` | Replaced with `NOASSERTION`, original value kept in the package's `sourceInfo` |
| Duplicate SPDXIDs, unknown relationship types, malformed `supplier`, missing `documentNamespace`, empty `creators`, missing DESCRIBES relationship | Deduplicated, reset or filled in as the spec requires |

The flag prints a summary of every category it changed, so nothing is altered silently.

**Filling in NOASSERTION values.** The SPDX export leaves `licenseConcluded`,
`licenseDeclared` and `downloadLocation` as `NOASSERTION`, but the CycloneDX export
of the *same* packageVersions carries both. The flag therefore also pulls the
CycloneDX export and fills those fields in:

| Field | Source | Coverage |
|---|---|---|
| `licenseConcluded` / `licenseDeclared` | CycloneDX `licenses[].license.name` | 73.5% of components |
| `downloadLocation` | CycloneDX `externalReferences[type=vcs].url` | 95.2% of components |
| `copyrightText` | `pkg_version_info_for_license` metric in the `oss` namespace | ~50% of components |
| `supplier` | the registry named by the package's purl | 100% of components with a purl |

Percentages are measured from real exports, not estimated, and vary by ecosystem
and project.

A field is only filled when it currently asserts nothing — a real value is never
overwritten — and filled licenses run through the same normalizer, so free text
becomes a proper identifier or a `LicenseRef`. Packages are matched on purl, falling
back to `name@version`. If the CycloneDX export fails the script says so and carries
on; the SBOM still validates, it just keeps its `NOASSERTION` values.

**Copyright notices** come from the `pkg_version_info_for_license` metric that
Endor computes for each OSS package version in its public `oss` namespace. The
SBOM export does not carry them, so the script resolves each purl to a package
version and reads the metric, batching 100 lookups per request. Roughly half of
packages have notices recorded; the rest keep `NOASSERTION`.

**Supplier** is set to the registry that distributed the package — `npmjs.com`,
`nuget.org`, `repo.maven.apache.org` and so on — taken from the purl's ecosystem.
SPDX defines supplier as the organization providing the package, and for an OSS
dependency the registry is what provided it, so this is a fact about the package
rather than a guess.

The alternative was inferring a supplier from each package's repository owner
(`github.com/facebook/react` → Facebook), which is more informative but only
works where a repo URL exists. Measured across real exports:

| Ecosystem | Supplier derivable from repository owner |
|---|---|
| npm | 96–99.7% |
| Go | 86–98% |
| Maven / Java | 64–82% |
| NuGet / .NET | **9–42%** |

That fails exactly where it is needed most, so it is not used. The registry is
known for every package that has a purl, which makes conformance reachable in
every ecosystem rather than only in npm.

**The root package** — the application the document describes — gets its supplier
from the organization configured in Endor's SBOM Settings, which the export
records in `creationInfo.creators` rather than on the package the conformance
checker reads. Endor supplies no version for that component either, so the
analyzed branch is used (`refs/heads/main` → `main`).

Note that `licenseConcluded` is filled with the declared license, matching what
`spdx_generator/create_spdx_sbom.py` already does. Strictly, "concluded" means the
SBOM author's own determination — if you would rather only assert `licenseDeclared`,
that is a one-line change in `_fill_licenses_from_record`.

**License list:** to tell a real SPDX identifier from free text, the script uses the
official SPDX license list. It is fetched once from `https://spdx.org/licenses/`
and cached in `.spdx_license_cache.json` next to the script — delete that file to
pick up a newer list. If the fetch fails the script falls back to a built-in set of
common identifiers and says so; licenses outside it become `LicenseRef-` entries,
which is still valid, just less precise.

### What has been verified

Validation, against 12 real SPDX exports spanning npm, Maven, Go and NuGet/.NET —
**all 12 validate with zero errors** after the flag runs:

| Export | Packages | Errors before | Errors after |
|---|---|---|---|
| npm (`sbom-export` API) | 633 | 777 | 0 |
| npm, large | 5,094 | 1,190 | 0 |
| Maven/Gradle, free-text licenses | 188 | could not be parsed at all | 0 |
| Go modules | 853 | 606 | 0 |
| NuGet/.NET | 1,387 | 1 | 0 |
| 7 others | 7 – 1,976 | 0 – 166 | 0 |

Enrichment, against the real CycloneDX export:

| Scenario | Licenses filled | `downloadLocation` filled | Errors |
|---|---|---|---|
| CycloneDX covers every package | 633/633 | 633/633 | 0 |
| Real CycloneDX, partial overlap | 210/633 | 210/633 | 0 |
| CycloneDX export fails | 0 | 0 | 0 |

The last row is the one that matters for safety: if the CycloneDX call fails the
script warns and carries on, and the SBOM still validates — it just keeps its
`NOASSERTION` values. Enrichment never blocks the output.

NTIA conformance, on the full pipeline (remove test dependencies → validate →
enrich) applied to the real `sbom-export` output:

| | Raw export | After the flag |
|---|---|---|
| SPDX validation | 777 errors | 0 |
| NTIA conformant | No — blocked by those errors | **Yes** |
| All seven elements present | Yes | Yes |

Verified end to end against a live `arsalan-learn` pull: 319 packages, 318
suppliers set from the registry plus the root package from the SBOM settings, 159
copyright notices filled, **0 validation errors and NTIA conformant**.

Note that Endor Labs has no supplier, author or maintainer field for OSS package
versions — confirmed across all 1,114 definitions in the API spec and against the
live `PackageVersion` schema. `supplier_name` exists only on imported SBOMs. That
is why the registry is used rather than a per-package supplier from the API.

Also checked: the input document is never mutated, every purl survives into
`externalRefs`, SPDXIDs stay unique after rewriting, and removing test
dependencies leaves no dangling references.

### Checking an SBOM locally

`validate_spdx.py` runs both of the online tool's checks — SPDX 2.3 validation
and NTIA minimum elements — so an SBOM can be confirmed without uploading it:

```
python validate_spdx.py <uuid>-original-spdx.json <uuid>-cleaned-spdx.json
python validate_spdx.py --no-ntia <uuid>-cleaned-spdx.json   # validation only
```

It groups validation messages by kind — hundreds of identical errors read as one
line — and exits non-zero if any file fails either check, so it drops straight
into CI. Expect `FAIL` on the original and `PASS` on the cleaned file; if both
pass, the project simply had none of the problem cases.

When every element is present but conformance still fails, the output says so
explicitly and names the number of validation errors blocking it, rather than
leaving a document that looks inexplicably non-conformant.

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
