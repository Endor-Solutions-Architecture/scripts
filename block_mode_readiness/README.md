# Block Mode Readiness Report

A **warn-to-block rollout** report for Endor Labs PR action policies (SCA, SAST, secrets, and anything else on the check). While policies are in **warn**, nothing stops a merge. Before you flip them to **block**, you need evidence from the actual PR checks on the repos in the rollout — not tenant-wide dashboards, and not a list of warned scans with no denominator.

This tool is a fit when you are rolling policies out to a **tagged project set** (the same tags used to enable repos and bind action policies) and you need a repeatable pack for a working session:

| Question | Where it lands |
|---|---|
| If we had been in block, what share of PR checks would have failed? | Section A — would-have-blocked %, with **all** PR checks as the denominator (including clean ones) |
| Is the friction everywhere, or a handful of repos? | Section B — concentration, including tagged repos with **zero** warns |
| Which PRs and findings should security label as true vs false positive? | `fp_worksheet.csv` — PR, finding, and scan links; blank `fp` / `reason` columns to fill and return |
| Are developers acting on warns (later scan, fewer findings)? | Section D — rescan trajectories (`acted` / `still_open` / `single_scan`). Not merge status. |
| What is the false-positive rate once labels come back? | Gate 1 in the PDF, from `--labels` on the returned worksheet |

Output is a branded PDF (meeting artifact) plus CSVs (the work). Re-run weekly: ScanResults last **21 days** in the API, so snapshots are the durable history of a rollout longer than that.

Scope is **project tags**, never the whole tenant as a silent fallback. If you do not yet know which tags define the rollout, list them first:

```bash
python list_project_tags.py -n example-corp
```

That prints a CSV of unique `Project.meta.tags` (traverses child namespaces) to stdout. Pick the rollout tag(s), then pass them as `--project-tags`.

## Prerequisites

- **Python 3.8+**
- **`endorctl`** on `PATH` and authenticated (`endorctl auth login`)
- Dependencies:

  ```bash
  pip install -r requirements.txt
  ```

Run commands from this directory (`block_mode_readiness/`).

## Quick start

Collect from the API and render a report for this pull only:

```bash
python main.py run -n example-corp \
  --project-tags rollout-wave-1 \
  --days 21
```

Full example with optional cover-page metadata and a policy enablement mark-date:

```bash
python main.py run -n example-corp \
  --project-tags rollout-wave-1 \
  --days 21 \
  --mark-date sast=2026-03-10 \
  --customer "Example Corp" \
  --decision-date 2026-06-01
```

Output lands under `generated_reports/block_mode_readiness/example-corp/<timestamp>/` (see [Snapshot layout](#snapshot-layout) below).

## Additive snapshot history

ScanResults are retained in the API for **21 days only**. **Snapshots are the durable history** of a rollout longer than that window.

**Do not delete old snapshot folders.** Each weekly `collect` (or `run`) writes a new timestamped folder; later collects never overwrite earlier ones. When the same scan UUID appears in multiple snapshots, union reporting keeps the **first** copy.

**Collect weekly from the first week of warn mode.** If the first collect happens late, PR checks from earlier weeks are **unrecoverable** from the API—the PDF will state that history starts at the first snapshot date, not at an assumed rollout start.

**Decision week:** union every weekly snapshot and render one pack:

```bash
python main.py report \
  --snapshot-dir generated_reports/block_mode_readiness/example-corp
```

This writes a new `union-<timestamp>/` folder under that directory (unioned PDF + CSVs). It does **not** modify existing collect folders.

**This week only:** `run` (or `collect` then `report --snapshot`) uses a single snapshot—fine for a spot check, not for the full rollout story.

If `--days` is greater than 21, the CLI warns and continues; the caveats page in the PDF notes API retention.

## CLI commands

| Command | Purpose |
|---|---|
| `collect` | Query the tenant via `endorctl`; write `snapshot.json` + `meta.json` only |
| `report --snapshot PATH` | One snapshot folder → PDF + CSVs (written into that folder) |
| `report --snapshot-dir DIR` | Union all collect snapshots under `DIR` → new `union-*` folder |
| `run` | `collect` + `report` for the current pull (single snapshot) |

`report` never calls the API. Re-rendering an old snapshot does not require scans to still exist in the tenant.

### Collect / run flags

| Flag | Meaning |
|---|---|
| `-n / --namespace` | **Required.** Tenant namespace for `endorctl`. |
| `--project-tags` | **Required.** Comma-separated **project** tags. Union of matching projects is the only scope (not finding tags). Exits with code 1 if zero projects match. |
| `--days` | Lookback window for this collect. Default `21`. Warn if greater than 21 (API retention). |
| `--mark-date KEY=YYYY-MM-DD` | Repeatable. Splits section A before/after that date (e.g. policy enablement: `sast=2026-03-10`). |
| `--customer` | Cover-page “Prepared for” text only. Default: the namespace. |
| `--decision-date YYYY-MM-DD` | Optional cover / next-steps date this pack informs. |

### Report flags

| Flag | Meaning |
|---|---|
| `--snapshot PATH` | Path to one snapshot directory (or its `snapshot.json`). |
| `--snapshot-dir DIR` | Directory containing one or more `<timestamp>/` collect folders (not `union-*`). Exits 1 if snapshots mix namespaces. |
| `--labels PATH` | Returned `fp_worksheet.csv` with `fp` and `reason` filled in; enables Gate 1 (false-positive rate) in the PDF. |

Example with returned labels:

```bash
python main.py report \
  --snapshot-dir generated_reports/block_mode_readiness/example-corp \
  --labels /path/to/returned_fp_worksheet.csv
```

## Snapshot layout

```text
generated_reports/block_mode_readiness/<namespace>/
  <timestamp>/                    # one weekly collect (or run)
    snapshot.json                 # raw API payload for analyze
    meta.json                     # namespace, tags, window, mark-dates, project count, …
    readiness_report.pdf          # after report
    pr_checks.csv
    fp_worksheet.csv
    pr_trajectories.csv
    summary.json
  union-<timestamp>/              # decision-week union report only
    readiness_report.pdf
    pr_checks.csv
    fp_worksheet.csv
    pr_trajectories.csv
    summary.json                  # no snapshot.json in union folders
```

`generated_reports/` is gitignored like other scripts in this repo.

## Output files

The PDF is the meeting artifact. The CSVs are the work.

### `pr_checks.csv`

One row per **PR check** on tagged projects in the window, **including clean scans**.

Columns: date, project_name, project_uuid, project_url, pr_number, pr_url, scan_result_url, outcome (`warn` / `block` / `clean`), warning_findings, blocking_findings, violation_types (pipe-separated), status.

Used for section A (would-have-blocked denominator and numerator) and section B (concentration, including repos with zero warns).

### `fp_worksheet.csv`

One row per **warning finding** on a warned scan.

Columns include date, project_name, pr_url, scan_result_url, finding_url, violation_type, policy, severity, finding, vuln_id, rule_id, package, reachable, fix_available, **`fp`** (blank until security returns the sheet), **`reason`** (blank until returned), plus `finding_uuid`, `scan_result_uuid`, `project_uuid` for joins.

Security engineering labels `fp` (true/false positive) and `reason`, then returns the file for `--labels`.

### `pr_trajectories.csv`

One row per PR that **warned at least once**: project_name, pr_url, first_scan, last_scan, scan_count, first_warning_count, last_warning_count, sequence (e.g. `3→3→1→0`), classification, first_scan_result_url, last_scan_result_url.

Used for section D and engineering drill-down.

### `summary.json`

Headline metrics for the PDF and week-over-week comparison. Ships in the folder; not the primary customer-facing artifact.

### `readiness_report.pdf`

Portrait, branded pack: cover, how to use, caveats, sections A–D, next steps.

## Definitions

### Would-have-blocked (section A)

**Numerator:** PR checks whose outcome is `warn` (and `block`, listed separately if any).  
**Denominator:** all CI PR checks on tagged projects in the window—**including clean scans**.

Only `ScanResult`s with a **`pr=`** tag on `context.tags` or `meta.tags` count toward A–D. Other CI runs are dropped (counted in `meta.json` as `ci_runs_dropped_no_pr`).

Rates are shown overall, by violation type, and before/after each `--mark-date`.

### Developer response (section D)

Endor-only, per `(project_uuid, pr_number)` among PRs that warned at least once. **Not merge behavior**—warn mode does not stop merges.

| Classification | Rule |
|---|---|
| `acted` | Two or more scans and **last** warning count **strictly less than** first |
| `still_open` | Two or more scans and last count did not drop |
| `single_scan` | Only one scan in available history |
| `cleared` | Subset of `acted`: last warning count is **0** |

Do not interpret `single_scan` as “ignored at merge.” Section D measures **rescan** trajectories, not GitHub merge status.

### False-positive rate (Gate 1, section C)

Blocked until `--labels` supplies filled `fp` values on the returned worksheet. The PDF reports per-finding and per-PR rollups (overall and by violation type). Unmatched label rows are listed, not silently dropped.

### Scope caveats

- **Project tags**, not finding tags—the rollout set is however repos are tagged for enablement and action policies. Discover tags with `python list_project_tags.py -n <namespace>`.
- **Warn mode** does not imply merge friction; developers can merge while checks warn.
- **21-day API retention**—long rollouts depend on weekly snapshots and decision-week `--snapshot-dir` union.

## Errors

The tool fails loud: no partial snapshot on collect failure, exit 1 if tags match zero projects, exit 1 if `--snapshot-dir` mixes namespaces. See stderr for the failing `endorctl` command when applicable.

## Tests

```bash
python -m pytest tests/ -v
```

Fixtures use fictional tenants only (e.g. `example-corp`, `rollout-wave-1`).

## No warranty

This software is provided on an "as is" basis, without warranty of any kind. You are solely responsible for determining whether this software is suitable for your use.
