# Quarterly Findings Report Design

## Purpose

Add a member-facing script that generates the two ITRON-derived CSV reports as a reusable Endor Labs internal tool:

1. **Fixed Findings**: vulnerability findings resolved within a requested date range.
2. **All Vulnerabilities**: all vulnerability findings that are open when the script runs.

The script must preserve the delivered CSV schemas and column ordering so existing pivot tables and dashboards continue to work. It must also support excluding tenant namespace subtrees without requiring users to edit the resulting CSVs manually.

## Location

Create a new tool directory:

```text
quarterly_findings_report/
├── README.md
├── main.py
├── requirements.txt
└── tests/
    └── test_main.py
```

The runtime implementation will use only the Python standard library and an authenticated `endorctl` installation. `pytest` is required only to run tests.

## Command-line interface

Example:

```bash
python main.py \
  --namespace itron \
  --start-date 2026-07-01 \
  --end-date 2026-09-30 \
  --exclude-namespace itron.test-1 \
  --exclude-namespace itron.test-2
```

Arguments:

- `-n`, `--namespace`: required root namespace to traverse.
- `--start-date YYYY-MM-DD`: required when generating Fixed Findings.
- `--end-date YYYY-MM-DD`: required when generating Fixed Findings.
- `--report {both,fixed,open}`: report selection; defaults to `both`.
- `--exclude-namespace NAMESPACE`: repeatable namespace-root exclusion.
- `--output-dir PATH`: destination directory; defaults to `generated_reports`.
- `--endorctl PATH`: executable name or path; defaults to `endorctl`.
- `--timeout-seconds N`: per-`endorctl` subprocess timeout with a conservative long-running default.

When `--report open` is selected, date arguments are optional and do not scope the open report. When `fixed` or `both` is selected, both dates are required.

The generated filenames remain compatible with the Ewok report names:

```text
fixed_findings.<namespace>.<YYYYMMDD_HHMMSS>.csv
all_vulns_all_levels.<namespace>.<YYYYMMDD_HHMMSS>.csv
```

## Date semantics

The CLI treats both dates as calendar dates in UTC and treats the supplied end date as inclusive.

For example:

```text
--start-date 2026-07-01 --end-date 2026-09-30
```

becomes the half-open API interval:

```text
spec.resolved_at >= date(2026-07-01T00:00:00.000Z)
spec.resolved_at <  date(2026-10-01T00:00:00.000Z)
```

The fixed report filters on `spec.resolved_at`, not FindingLog `meta.create_time`.

The open report is explicitly a **current-open snapshot**. The date range does not attempt to reconstruct which findings were open at a historical quarter end. The script and README must state this distinction clearly.

## Namespace exclusions

Each `--exclude-namespace` value excludes:

- the exact namespace; and
- every descendant namespace separated by `.`.

For example, excluding `itron.test-2` removes both `itron.test-2` and `itron.test-2.uiq`, while retaining similarly prefixed namespaces such as `itron.test-20`.

Exclusions apply to both generated reports. They are implemented centrally against each object's `tenant_meta.namespace`, before row generation.

No customer-specific namespace is hard-coded.

## Authentication and data access

The script delegates authentication and API pagination to the member's existing `endorctl` installation. It does not read, persist, or print tokens or API secrets.

At startup it verifies:

```bash
endorctl --version
```

API calls use argument arrays with `subprocess`, never `shell=True`.

The script uses direct resource list calls rather than Ewok's Query service:

- `FindingLog` for Fixed Findings.
- `Finding` for the current-open report.
- `Project` for project-name enrichment.
- `PackageVersion` for package-name enrichment.

Calls use `--list-all`, `--traverse`, focused field masks, and explicit command timeouts. Transient command failures receive bounded exponential-backoff retries. Permanent failures end with a non-zero exit code and do not publish a partial final CSV.

## Fixed Findings retrieval

The FindingLog filter contains:

```text
context.type==CONTEXT_TYPE_MAIN
spec.operation==OPERATION_DELETE
spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]
spec.finding_tags contains [FINDING_TAGS_NORMAL]
spec.resolved_at >= <start>
spec.resolved_at < <day-after-end>
```

The script requests only fields required by the 19-column output.

### Fixed Findings CSV contract

Columns, in this exact order:

1. `Namespace`
2. `Parent Namespace`
3. `Finding UUID`
4. `Description`
5. `Severity`
6. `Dependency Name`
7. `Introduced Date`
8. `Resolved Date`
9. `Days Unresolved`
10. `Ecosystem`
11. `Finding Tags`
12. `Finding Categories`
13. `Approximation`
14. `Finding Log UUID`
15. `Finding Log Name`
16. `Finding Parent Kind`
17. `Finding Parent UUID`
18. `Project UUID`
19. `Project Name`

`Project Name` remains blank for parity with the previously delivered fixed report. The column remains present.

## All Vulnerabilities retrieval

The Finding filter contains:

```text
context.type==CONTEXT_TYPE_MAIN
spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]
spec.finding_tags contains [FINDING_TAGS_NORMAL]
spec.finding_tags not contains [FINDING_TAGS_EXCEPTION]
spec.finding_tags not contains [FINDING_TAGS_TEST]
spec.level in [
  FINDING_LEVEL_CRITICAL,
  FINDING_LEVEL_HIGH,
  FINDING_LEVEL_MEDIUM,
  FINDING_LEVEL_LOW
]
```

The script enriches findings as follows:

- `Project Name`: map `spec.project_uuid` to Project `meta.name`.
- `Package Name`: map Finding `meta.parent_uuid` to PackageVersion `meta.name`.

Enrichment lookups are deduplicated and batched. Missing references produce empty values without changing the CSV schema.

### All Vulnerabilities CSV contract

Columns, in this exact order:

1. `Namespace`
2. `Parent Namespace`
3. `Finding UUID`
4. `Description`
5. `Severity`
6. `Create Time`
7. `Dependency Name`
8. `Dependency Version`
9. `Aliases`
10. `CVSS Score`
11. `EPSS Probability`
12. `Relationship`
13. `Remediation Text`
14. `Package UUID`
15. `Package Name`
16. `Project UUID`
17. `Project Name`
18. `Finding Tags`
19. `Has CI Blocker`
20. `Has CI Warning`
21. `Has Direct`
22. `Has Disputed`
23. `Has Exception`
24. `Has Exploited`
25. `Has Fix Available`
26. `Has Invalid Secret`
27. `Has Malware`
28. `Has Namespace Internal`
29. `Has Normal`
30. `Has Notification`
31. `Has Path External`
32. `Has Phantom`
33. `Has Policy`
34. `Has Potentially Reachable Dependency`
35. `Has Potentially Reachable Function`
36. `Has Project Internal`
37. `Has Reachable Dependency`
38. `Has Reachable Function`
39. `Has Self`
40. `Has Test`
41. `Has Transitive`
42. `Has Under Review`
43. `Has Unfixable`
44. `Has Unreachable Dependency`
45. `Has Unreachable Function`
46. `Has Valid Secret`
47. `Has Withdrawn`

The `Has ...` fields are integer `1`/`0` values derived from `spec.finding_tags`.

## CSV value compatibility

The script writes UTF-8 CSV with Python's `excel` dialect and `newline=""`.

Compatibility rules:

- Headers and ordering are constants, not inferred dynamically.
- Missing values become empty strings.
- Lists are passed to `csv.writer` as Python lists so their representation matches the prior Ewok output.
- Booleans retain Python `True`/`False` text.
- Tag indicator columns use integer `1` and `0`.
- Row ordering follows API order; consumers must not depend on row order.

`Parent Namespace` uses the first two dot-separated components. A namespace without a dot yields an empty parent namespace, matching the ITRON implementation.

## Reliability and file publication

Each external command:

- has a configurable timeout;
- retries transient non-zero failures a bounded number of times;
- uses exponential backoff;
- reports the resource and attempt without exposing credentials.

Each CSV is first written to a temporary file in the output directory. After all rows are written and validation succeeds, the temporary file is atomically renamed to its final filename.

If `--report both` is used and one report fails, the command exits non-zero and clearly identifies which report failed. A successfully completed report may remain available, but no temporary or malformed file is presented as final.

At completion, the script prints:

- output path;
- row count;
- excluded-row count;
- fixed-report minimum and maximum resolved timestamps;
- report snapshot time for the open report.

## Validation

Before publishing:

- the emitted header must exactly equal the corresponding 19- or 47-column constant;
- no row may belong to an excluded namespace subtree;
- every Fixed Findings row must satisfy the requested resolved-date interval;
- every open row must satisfy the vulnerability, severity, Normal, not-Test, and not-Exception predicates represented by the report.

Validation failures remove the temporary output and return a non-zero exit code.

## Tests

Tests use fixtures and a fake `endorctl` executable/subprocess runner; they do not call the live API.

Required coverage:

- inclusive CLI end date converted to an exclusive next-day boundary;
- invalid and reversed date ranges;
- dates required only when Fixed Findings is selected;
- exact and descendant namespace exclusion;
- similarly prefixed namespaces retained;
- fixed API filter uses `spec.resolved_at`;
- open API filter represents current-open semantics and all four levels;
- exact 19- and 47-column headers and order;
- parent-namespace derivation;
- fixed-record transformation;
- open-record transformation and nested vulnerability metadata;
- all 29 tag indicator columns;
- missing project/package enrichment;
- batched enrichment lookup behavior;
- retry success and exhausted-retry failure;
- atomic CSV publication and cleanup after failure;
- CLI output paths and exit codes.

The new tool's test suite is run independently because the repository currently has a pre-existing root pytest collection collision between two unrelated `test_compute.py` modules.

## Documentation

`quarterly_findings_report/README.md` will document:

- prerequisites and `endorctl` authentication;
- installation (no runtime Python packages);
- examples for both/fixed/open modes;
- inclusive date behavior;
- current-open versus historical-open semantics;
- repeatable namespace exclusions;
- exact output filenames and column contracts;
- expected runtime for large tenants;
- retry/timeout troubleshooting;
- the no-warranty statement used by other scripts in this repository.

## Non-goals

- Reconstructing a historical open-findings snapshot.
- Hard-coding ITRON or any customer namespace.
- Changing or replacing Ewok.
- Producing dashboards, PDFs, or aggregate summaries.
- Modifying findings or any other Endor resource.
