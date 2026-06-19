# Project Findings with Vulnerability Disclosure

Standalone Python port of the ewok report
`project_findings_with_vulnerability_disclosure`. Generates a CSV listing
every project in a namespace alongside its monthly Critical / High /
Medium / Low vulnerability finding counts, the most-recent scan date,
and the most-recent scan date from a previous calendar month.

## CSV columns

```
Namespace, Project UUID, Project Name, C, H, M, L, Last scan date, Last month last scan date
```

These match the ewok report byte-for-byte.

## Prerequisites

- Python 3.10+
- Endor Labs **API key + secret** (created at *Settings → API Keys* in the
  Endor Labs UI). The key must have read access to projects, scan results,
  and findings in the target namespace.

## Setup

```bash
cd /Users/arsalanendor/Documents/GitHub/scripts/project_findings_vuln_disclosure

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and fill in real credentials
```

`.env` must contain (at minimum):

```
API_KEY=<YOUR_KEY>
API_SECRET=<YOUR_SECRET>
ENDOR_NAMESPACE=<YOUR_TENANT_NAMESPACE>
```

Optional: `ENDOR_API_URL` if you target a non-default Endor instance.

## Usage

```bash
python main.py
```

That runs the report against the namespace declared in `.env` and writes the
output to `./generated_reports/project_findings_with_vulnerability_disclosure.<namespace>.<YYYYMMDD_HHMMSS>.csv`.

### Flags

```
-n / --namespace NS         override ENDOR_NAMESPACE for this run
--env-file PATH             alternate .env file (default: ./.env)
--findings-month YYYY-MM    month for the C/H/M/L finding counters
--last-period-month YYYY-MM month for the "Last month last scan date" column
--month YYYY-MM             shortcut: apply the same month to both windows
--output-dir DIR            where to write the CSV (default: ./generated_reports)
--api-url URL               override Endor API base URL
--page-size N               graph query page size (default: 25)
--dump-query                render the query JSON and exit, no API call
```

By default the script uses the **same hardcoded date windows the ewok query
file ships with**, so running with no flags here produces the same windows
that ewok produces with no edits:

- C / H / M / L finding counts: `2025-12-01 .. 2025-12-31`
- `LastPeriodScanResult` ("Last month last scan date"): `2026-02-01 .. 2026-02-28`

This is intentional: it lets you run both ewok and this script side by
side and diff the CSVs. Pass `--findings-month` / `--last-period-month` /
`--month` to override.

### Examples

```bash
# Default: ewok-identical date windows, namespace from .env
python main.py

# Override both windows to a single month
python main.py --month 2025-12

# Override windows separately
python main.py --findings-month 2025-12 --last-period-month 2026-02

# Different namespace, dump query JSON for inspection (no API call)
python main.py -n acme.team-a --month 2025-12 --dump-query
```

## How it works

1. Loads `.env` (or `--env-file`) into the process environment without
   overriding existing variables.
2. Exchanges `API_KEY` / `API_SECRET` for a short-lived JWT via
   `POST /v1/auth/api-key`.
3. Renders `query.project_findings_with_vulnerability_disclosure.json`,
   substituting placeholders for the two date ranges and the namespace.
4. Pages through `POST /v1/namespaces/<namespace>/queries` using
   `next_page_token`, traversing descendant namespaces.
5. Flattens each `meta.references[*].list.objects[0]` into the parent
   reference object — same normalization ewok performs — so the dot-paths
   `meta.references.<Name>.count_response.count` and
   `meta.references.<Name>.spec.start_time` resolve cleanly.
6. Writes the 9-column CSV.

## Query template

The query lives in
`query.project_findings_with_vulnerability_disclosure.json`. It is the
same shape as the in-tree ewok query, with these placeholders rendered at
runtime:

- `__FINDINGS_START__` / `__FINDINGS_END__` — date window for
  Critical / High / Medium / Low finding counts
- `__LAST_PERIOD_START__` / `__LAST_PERIOD_END__` — date window for
  `LastPeriodScanResult`

Edit the JSON directly if you need to change other filters (e.g. add or
remove `FINDING_TAGS_NORMAL`).

## No warranty

This software is provided on an "as is" basis, without warranty of any
kind. You are solely responsible for determining whether this software is
suitable for your use.
