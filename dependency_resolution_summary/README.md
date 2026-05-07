# Dependency Resolution & Reachability Summary Report

Generates a CSV (and PDF) summarizing dependency-resolution and reachability outcomes for every project in a namespace. Member-facing port of the internal ewok `report dependency_resolution_summary` command.

## Features

- Single graph query — one round-trip per page of projects.
- CSV output with 15 columns (namespace, project, totals, %s, category, reachability strategy, error notes, tags).
- PDF output with executive summary, progress bars, reachability strategy breakdown, and three categorized project tables (full success / dependency issues / reachability-only issues).
- Authenticates via your already-signed-in `endorctl` (`endorctl auth --print-access-token`).

## Prerequisites

- Python 3.10+ (uses PEP 604 union types like `str | None`)
- `endorctl` installed and authenticated (`endorctl auth login`).
- `libcairo` (only needed to render the Endor logo on the PDF; the PDF still produces without it). On macOS: `brew install cairo`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

From inside this directory:

```bash
python main.py -n <namespace>
```

Or from the parent `scripts/` directory:

```bash
python -m dependency_resolution_summary.main -n <namespace>
```

Common flags:

```
-n / --namespace     required — tenant or sub-namespace
--output-dir DIR     default: ./generated_reports
--api-url URL        default: https://api.endorlabs.com (or $ENDOR_API_URL)
--no-pdf             skip PDF, write CSV only
--page-size N        default: 100
--token TOKEN        override token (otherwise ENDOR_TOKEN or endorctl)
```

Examples:

```bash
# Default: write both CSV and PDF for the whole tenant
python main.py -n acme

# CSV only, into a custom directory
python main.py -n acme.team-a --output-dir /tmp/reports --no-pdf
```

## Output

Files land in `--output-dir` (default `./generated_reports/`):

```
dependency_resolution_summary.<namespace>.<YYYYMMDD_HHMMSS>.csv
dependency_resolution_summary.<namespace>.<YYYYMMDD_HHMMSS>.pdf
```

CSV columns:

`Namespace, Project UUID, Project Name, Project URL, Total Packages, Dependency Resolution Success, Dependency Resolution Failed, Reachability Success, Reachability Failed, Dependency Resolution %, Reachability %, Category, Reachability Strategy, Error Notes, Tags`

`Category` values:
- `full_success` — all packages resolved and reachability analysis succeeded
- `dependency_resolution_issues` — at least one package failed to resolve
- `reachability_issues_only` — dependencies resolved but reachability analysis failed for some package(s)

`Reachability Strategy` (only for `full_success` and `reachability_issues_only`):
- `FULL` — full call-graph analysis without fallback
- `PRE-COMPUTED` — used precomputed reachability fallback when call-graph analysis failed for at least one package

## How It Works

1. Resolves a JWT bearer token: `--token` → `ENDOR_TOKEN` → `endorctl auth --print-access-token`.
2. Loads the graph query JSON from `query.dependency_resolution_summary.json` (kept byte-identical to the ewok source for easy diffing).
3. POSTs the query to `/v1/namespaces/<namespace>/queries`, paging via `next_page_token`.
4. Categorizes each project, computes percentages, derives the reachability strategy from per-package `precomputed_call_graph_state`, and extracts human-readable error notes from `spec.resolution_errors`.
5. Writes the CSV, then renders the PDF unless `--no-pdf`.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## No Warranty

This software is provided on an "as is" basis, without warranty of any kind. You are solely responsible for determining whether this software is suitable for your use.
