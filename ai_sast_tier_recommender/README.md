# AI SAST Tier Recommender

Interactive Streamlit tool that recommends an AI SAST **tier (1/2/3)** per
repository in a namespace, maximizing security value while fitting the
tenant's AI credit budget. It produces an **explainable rationale per repo**
so a CSE can justify the plan to the customer.

**Advisory only** — it never applies scan profiles or changes quota. It is the
tier-planning companion to the spend dashboard (`../ai_credit_dashboard`); see
the design spec at `monorepo/doc/ai-sast-tier-recommender-spec.md` and the
strategy in `monorepo/doc/ai-sast-rollout-guide.md`.

## Prerequisites

- `endorctl` installed and available in your PATH
- Authenticated to the target tenant (query at the **root** namespace)
- Python 3.9+

## Usage

```bash
pip install -r requirements.txt
streamlit run dashboard.py   # serves on http://localhost:8502
```

Runs on port **8502** (pinned in `.streamlit/config.toml`) so it can run
alongside the spend dashboard (`../ai_credit_dashboard`, default 8501). Override
with `streamlit run dashboard.py --server.port <port>`.

In the sidebar: enter the root tenant namespace, click **Generate/Refresh**,
then tune the allocation knobs — re-allocation is instant (client-side, no
re-fetch).

## The tiers (from the rollout guide)

| Tier | SAST configuration | Pool cost |
|------|--------------------|-----------|
| **Tier 1** | AI SAST agent (exploitability-aware) | Highest — scales with codebase size |
| **Tier 2** | Rule-based SAST + AI false-positive triage | Medium — scales with # findings |
| **Tier 3** | Rule-based (Opengrep) rules only | Zero (free of the pool) |

## How it decides

1. **Language gate (hard):** repos whose supported-language **byte share**
   (`Repository.spec.languages`) is below the threshold (default 50%) go
   straight to **Tier 3** — AI SAST can't help them.
2. **Value score (0–1):** a tunable blend of commit **activity**
   (`Metric` TimeTracker), high-severity **SAST findings** on the default branch
   (SCA/secrets excluded), and **release/production** signal (release tags +
   monitored-version count).
3. **Cost estimate:** a global blended `$/KLOC` (from observed spend ÷ scanned
   KLOC) scaled by repo size and a monitored-version multiplier. See the
   important cost caveats below.
4. **Greedy allocation:** repos are ranked by **value ÷ cost** and promoted to
   **Tier 1** until the budget (minus a safety margin) is committed; remaining
   eligible repos with findings become **Tier 2**; the rest **Tier 3**. Tier 1
   and Tier 2 share the one budget.

## Tunable knobs (sidebar)

Budget, safety margin, language-gate threshold, monitored-version multiplier
`k`, value weights (activity / findings / release), and cost calibration
(**multiselect the repos you've already AI-SAST scanned** — the tool sums their
supported-language size automatically and derives `$/KLOC` from observed spend;
no manual line-count entry). A **per-tier filter** narrows the recommendations
table. All controls re-allocate client-side.

## Export

CSV (full recommendation table) and a branded PDF (estate summary, tier
distribution, and the per-repo recommendations).

## How it works

One `endorctl` pull per "Generate" (repositories, monitored-version counts,
metrics, findings, license, observed spend), cached in the browser session and
re-allocated client-side as the knobs change.

```bash
# Reference commands the tool wraps:
endorctl -n <ns> api list -r EndorLicense --field-mask "spec.quota.ai_limit"
endorctl -n <ns> api list -r Repository \
  --field-mask "meta.name,meta.parent_uuid,spec.languages,spec.tags,spec.default_branch" --list-all
endorctl -n <ns> api list -r RepositoryVersion --field-mask "meta.parent_uuid" --list-all
endorctl -n <ns> api list -r Metric --field-mask "meta.parent_uuid,spec.metric_values" --list-all
endorctl -n <ns> api list -r Finding \
  --filter "context.type == CONTEXT_TYPE_MAIN and (spec.level == FINDING_LEVEL_CRITICAL or spec.level == FINDING_LEVEL_HIGH) and spec.finding_categories contains [FINDING_CATEGORY_SAST]" \
  --field-mask "spec.project_uuid" --list-all
endorctl -n <ns> api list -r AICreditMetric \
  --filter "spec.accrued_date >= <cutoff>" --field-mask "spec.llm_cost" --list-all
```

## Known limitations (important)

- **Cost is coarse.** `AICreditMetric` spend is only available aggregated at
  the **tenant/day/model** level — `ai_feature` is never populated and there is
  **no per-repo attribution**. So the `$/KLOC` rate is a single blended,
  tenant-wide figure scaled by size — planning-grade, not exact. Lean on the
  safety margin. When no already-scanned repos are selected, cost falls back to
  coarse size buckets with a low-confidence banner.
- **Findings are high/critical SAST on the default branch**, joined via
  `spec.project_uuid` (the stable key the platform uses), scoped to
  `context.type == CONTEXT_TYPE_MAIN` so they aren't multiplied across monitored
  release branches. SCA/secrets are excluded — AI SAST doesn't address them.
- **Activity is best-effort.** `Metric` has a generic parent, so commit-activity
  parsing is defensive and defaults to 0 (flagged) rather than failing the run.
- **Quota must be configured.** With `days == 0` / `max_credit == 0` there is
  no budget to fit (and no usage is metered either) — the tool stops and says so.
- **Advisory only** — assign the recommended tiers via scan profiles yourself.

## Tests

```bash
pip install pytest
pytest
```

`compute.py` holds all logic (pure, no I/O) and is fully unit-tested; all
`endorctl`/Streamlit I/O lives in `dashboard.py`.
