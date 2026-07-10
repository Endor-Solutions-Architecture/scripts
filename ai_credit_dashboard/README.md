# AI Credit Usage Dashboard

Interactive Streamlit dashboard for visualizing a tenant's AI SAST / LLM-backed
feature credit usage against its quota: current usage vs. limit, burn rate,
projected exhaustion date, and a per-model breakdown, over selectable lookback
windows.

Read-only — this tool does not modify quota or usage. It's an interim bridge
until first-party in-app visibility ships (see the companion problem
statement at `monorepo/doc/ai-sast-usage-visibility-tool-spec.md`).

## Prerequisites

- `endorctl` installed and available in your PATH
- Authenticated to the target tenant
- Python 3.8+

## Usage

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

In the sidebar: enter the root tenant namespace and click **Generate/Refresh
Report**.

## What it shows

**Quota Summary** (always uses the tenant's actual enforcement window —
`EndorLicense.spec.quota.ai_limit.days` — not the explorer preset below):
- % of quota used, credits used / max, remaining credits
- Threshold band (🟢 OK <50%, 🟡 Warning 50-80%, 🟠 High 80-95%, 🔴 Critical 95%+),
  mirroring the platform's alert thresholds
- Burn rate: trailing 14-calendar-day average daily cost
- Projected exhaustion date at the current burn rate (or "negligible burn" if
  usage is near zero)
- A warning banner if the tenant's quota window exceeds 180 days (e.g. a
  placeholder config like `days: 1000`) — the headline number in that case
  only reflects the last 180 fetched days, not the full rolling window

**Explorer** (user-selectable lookback, independent of the quota window):
Last 1 day, 7 days, 2 weeks, 4 weeks, 2 months, 3 months.
- Daily cost trend chart with a cumulative-sum line vs. the `max_credit`
  reference line
- Per-model (`llm`) cost breakdown
- Raw daily data table

**Export:** CSV (selected window) and branded PDF (quota-window headline metrics, selected-window trend chart and model breakdown).

## How it works

One `endorctl` pull of `AICreditMetric` per "Generate/Refresh" — capped at
`min(max(license_days, 90), 180)` days — cached in the browser session and
sliced client-side for every view. Changing the explorer's lookback preset
does not trigger a new `endorctl` call.

```bash
# Reference commands the dashboard wraps:
endorctl api list -r EndorLicense --field-mask="spec.quota.ai_limit"
endorctl api list -r AICreditMetric \
  --filter "spec.accrued_date >= <cutoff>" \
  --field-mask "spec.llm_cost,spec.accrued_date,spec.llm" \
  --list-all
```

`spec.llm_cost` (dollars) is the authoritative cost field —
`spec.total_credit_count` (tokens) is input-only and is never used.

## Known limitations

- No per-feature (`ai_feature`) breakdown: confirmed live that this field is
  never populated on `AICreditMetric`, so usage can only be broken down by
  model, not by feature (AI SAST vs. Security Review, etc.).
- No rollout forecast estimator (what-if sliders for onboarding N repos) —
  deferred; this dashboard covers historical usage only.
- No per-repo/per-project cost attribution — `AICreditMetric` is aggregated
  at the tenant/day/model level, not per project.
