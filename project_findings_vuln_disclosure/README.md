# Project Findings with Vulnerability Disclosure

Standalone Python port of the ewok report
`project_findings_with_vulnerability_disclosure`. Generates a CSV listing
every project in a namespace alongside its Critical / High / Medium /
Low vulnerability finding counts for a configurable reporting window,
the most-recent scan date ever, and the most-recent scan date that
falls inside the reporting window.

By default the reporting window is the trailing 30 days ending today,
so running the script on the 1st of a month produces ~one month of
data. The window is overridable on the CLI — see the
[Usage](#usage) section.

## CSV columns

```
Namespace, Project UUID, Project Name, C, H, M, L, Last scan date, Last month last scan date
```

Column headers match the ewok report exactly. The numeric values match
ewok byte-for-byte when both are pointed at the same date window (see
[Usage](#usage)).

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
-n / --namespace NS       override ENDOR_NAMESPACE for this run
--env-file PATH           alternate .env file (default: ./.env)
--start-date YYYY-MM-DD   start of the reporting window (default: today - 30 days)
--end-date   YYYY-MM-DD   end of the reporting window   (default: today)
--month      YYYY-MM      shortcut: first-through-last day of that calendar month
--output-dir DIR          where to write the CSV (default: ./generated_reports)
--api-url URL             override Endor API base URL
--page-size N             graph query page size (default: 25)
--dump-query              render the query JSON and exit, no API call
```

By default the report covers **the trailing 30 days ending today**:

- end date = `today`
- start date = `today - 30 days`

The same window is applied to the C / H / M / L finding counters **and**
to the `LastPeriodScanResult` reference (the "Last month last scan date"
column), so the whole CSV talks about the same time slice.

Running this on the 1st of a month therefore approximates "all findings
created and all scans run during the previous month" (e.g. running on
June 1 produces a `May 2 .. June 1` window). It is a sliding 30-day
window, not strict calendar-month boundaries — use `--month YYYY-MM` if
you need exact month edges.

The `Last scan date` column (the `MostRecentScanResult` reference) has
**no** date filter and always returns the most recent scan ever, by
design.

### Examples

```bash
# Default: trailing 30 days ending today, namespace from .env
python main.py

# Same period the customer would expect "for May 2026"
python main.py --month 2026-05

# Explicit custom window
python main.py --start-date 2026-04-15 --end-date 2026-05-15

# Different namespace, dump query JSON for inspection (no API call)
python main.py -n acme.team-a --dump-query
```

## How it works

1. Loads `.env` (or `--env-file`) into the process environment without
   overriding existing variables.
2. Exchanges `API_KEY` / `API_SECRET` for a short-lived JWT via
   `POST /v1/auth/api-key`.
3. Renders `query.project_findings_with_vulnerability_disclosure.json`,
   substituting the reporting-window dates and the namespace.
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

- `__FINDINGS_START__` / `__FINDINGS_END__` — date window for the
  Critical / High / Medium / Low finding counters.
- `__LAST_PERIOD_START__` / `__LAST_PERIOD_END__` — date window for the
  `LastPeriodScanResult` reference (the "Last month last scan date"
  column).

The CLI stamps the same start/end into both pairs of placeholders, so
the whole CSV reflects a single reporting window. The placeholders are
kept separate in the JSON so the windows can be hand-edited apart if you
ever need them to diverge again (as the original ewok JSON did). Edit
the JSON directly if you also need to change other filters (e.g. add or
remove `FINDING_TAGS_NORMAL`).

## No warranty

This software is provided on an "as is" basis, without warranty of any
kind. You are solely responsible for determining whether this software is
suitable for your use.
