# Final Fix Report: Block Mode Readiness

## Status

All requested Critical and Important whole-branch review findings are fixed on
`feat/block-mode-readiness`. The implementation remains client-agnostic and
does not modify `pr_block_warn_report`.

## What changed

- Collection now validates the complete `list.objects` response shape and every
  returned object type inside the retry boundary. Malformed responses raise
  `CollectError` with the full `endorctl` command instead of becoming an empty
  result.
- Finding chunk lookups verify that every requested UUID was returned. Missing
  UUIDs abort collection with the failing command.
- Policy collection requests `spec.project_exceptions` and lists a policy only
  when it applies to at least one selected, non-excluded project.
- Returned labels are read as `utf-8-sig`, require the join and label columns,
  reject blank or duplicate join keys, and convert file/encoding/CSV failures
  into a clean CLI exit 1.
- Collect and union output directories are atomically reserved. Same-second
  collisions receive deterministic numeric suffixes and cannot overwrite an
  earlier snapshot.
- PDF rates now show labeled numerator/denominator counts for Gate 1 overall
  and by violation type at both finding and PR grain. Mark-date splits show
  explicit warn percentages and block counts, concentration names K (up to the
  top 5) and shows warn counts, and repository rates carry counts.
- PDF customer, policy, repository, and table text is HTML-escaped. Table cells
  use wrapping `Paragraph` flowables.
- README wording now says the decision-week PDF and CSVs are “unioned.”

## Covering tests

- Malformed/missing `list.objects`, invalid object members, retry behavior, and
  attached `ScanResult` command.
- Finding response missing one requested UUID.
- Policy excluded through `project_exceptions`.
- UTF-8 BOM labels, missing required columns, duplicate and conflicting join
  keys, plus clean CLI handling for missing/invalid label files.
- Same-timestamp collect calls reserve two distinct snapshot directories.
- Gate 1 labeled counts, per-type PR rollups, zero-label denominators,
  mark-date block counts, concentration counts, and escaped long PDF text.

## Verification

Command:

```text
cd block_mode_readiness && python -m pytest tests/ -v
```

Output:

```text
collected 70 items
70 passed in 1.42s
```

Additional checks:

```text
python -m compileall -q block_mode_readiness
git diff --check
IDE lints: no errors
```

## Concerns

No live-tenant call was made; collection behavior is covered by deterministic
fake `endorctl` responses as required by the spec.
