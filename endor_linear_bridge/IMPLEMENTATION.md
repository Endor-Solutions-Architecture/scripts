# Endor Linear Bridge — Implementation Overview & Support Matrix

High-level description of how the bridge works, the design decisions behind
it, and exactly what is and is not supported. For day-to-day operation see the
[README](README.md); for step-by-step setup see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## What it is

A customer-deployable middleware service that receives Endor Labs webhook
notifications and maintains Linear issues. Endor Labs ships first-class
ticketing integrations for Jira and Azure DevOps Boards but not Linear; the
bridge fills that gap **with no Endor product changes** — it consumes the
standard webhook notification plugin, shaped by three custom templates.

For every Endor notification stream it maintains:

- **One parent issue per (project, context/branch, Linear team)** — e.g.
  `[Endor Labs] webapp — main`
- **One sub-issue per dependency with findings** — e.g. `[Dep] npm://lodash`

with the full lifecycle automated: created on OPEN, description rewritten and
commented on UPDATE, closed (with parent auto-close) on RESOLVE.

## Core design decisions

| Decision | Choice |
|---|---|
| Deliverable | Middleware only — no Endor product changes, no Linear app |
| Runtime | Python 3.12 / FastAPI, SQLAlchemy 2.x, hand-written Linear GraphQL client (8 operations) |
| State store | SQLite by default (WAL mode); Postgres supported via `database_url` |
| Team routing | One Endor webhook target per Linear team → `POST /hooks/{team_key}`; routing lives in Endor policy scoping |
| Aggregation | `AGGREGATION_TYPE_DEPENDENCY_ACROSS_PKG_VERSIONS` (one notification per dependency) |
| Issue grouping | Parent keyed on `(project_uuid, context_id, team_key)` |
| Resolve behavior | Move to a `completed`-type workflow state + resolution comment (Linear has no transition graph to navigate) |
| Linear auth | Workspace/personal API key |
| Endor auth | Bearer token + mandatory per-team HMAC (`base64(HMAC-SHA256(raw_body, secret))`), verified on raw bytes with constant-time comparison |

## Architecture

```
Endor (endorctl or cloud) ──HTTPS+HMAC──▶ FastAPI app (app.py)
                                             │  auth → envelope parsing → dispatch
                                             ▼
                                        handlers.py  (lifecycle orchestration)
                                        │        │
                              store.py (SQL)   linear_client.py (GraphQL)
                                        │        │
                                     SQLite    Linear API
```

Strict module boundaries: only `store.py` contains SQL, only
`linear_client.py` contains GraphQL, `handlers.py` contains neither. Issue
content always renders from the finding rows in the database — never from a
single webhook payload — because Endor's UPDATE payloads carry only *new*
findings.

Four small tables: `project_parents` (parent issues), `notification_issues`
(sub-issues, keyed by Endor notification UUID), `notification_findings` (the
union of findings ever reported per notification), `processed_events`
(idempotency ledger keyed on notification + event + payload hash).

## Reliability model

The bridge assumes every delivery can be a retry and every request can crash
mid-flight:

- **Idempotency ledger.** Redelivery of an identical payload is a no-op; a
  genuinely different UPDATE for the same notification still processes.
- **Crash-safe issue creation (two-phase).** A `pending` row is committed
  *before* the first Linear call, and Linear issue ids are committed the
  moment they are known. Every issue description carries recovery footers
  (`Endor-notification-uuid:` etc.); a retry that finds a pending row searches
  Linear for the footer and **adopts** the orphaned issue instead of creating
  a duplicate. The happy path pays no search cost.
- **Single-flight parent creation.** Overlapping deliveries for the same
  project are serialized through an in-process lock, so concurrent OPENs
  cannot double-create a parent issue. (This is one reason the service must
  run as a single instance with one worker.)
- **Deliberate HTTP semantics toward Endor.** 4xx is reserved for problems a
  retry cannot fix (bad auth, malformed payload, unknown team) — Endor treats
  those as permanent. Everything else, including Linear outages and unexpected
  exceptions, returns 503 so Endor retries at 1h/2h/4h.
- **Linear rate limiting.** 429/5xx responses are retried in-process with
  jittered exponential backoff before surfacing as 503.
- **Regressions get a new sub-issue.** A dependency that is fixed and later
  regresses arrives as a new Endor notification UUID; the closed sub-issue
  stays as history and a fresh one is created under the same parent.

## Security

- Secrets exclusively via environment variables; `config.yaml` names
  variables, never values. Nothing secret is ever logged.
- HMAC is mandatory per team — there is no opt-out in the bridge.
- TLS is terminated in front of the service (ingress/tunnel); the container
  runs as a non-root user.

## Observability

- Structured JSON logs, every line keyed by `notification_uuid`, `team_key`,
  `event`, and the Linear identifier where known.
- Prometheus metrics: `events_received_total{team,event}`,
  `events_failed_total{team,event,reason}`, `linear_api_latency_seconds`,
  `linear_rate_limit_remaining`.
- `/healthz` (liveness) and `/readyz` (DB + Linear caches loaded).

---

## What is currently supported

| Capability | Status |
|---|---|
| OPEN → parent + sub-issue creation | ✅ Supported — **verified against a live tenant and Linear workspace (2026-07-29)** |
| UPDATE → description rewrite from finding union, new-findings comment, severity/priority recompute | ✅ Supported — covered by the test suite; live delivery not yet exercised |
| RESOLVE → close sub-issue, auto-close parent when last child resolves | ✅ Supported — covered by the test suite; live delivery not yet exercised |
| Reopen: new findings against a resolved parent/sub-issue | ✅ Supported (reopen state + comment) |
| Multiple Linear teams from one bridge instance | ✅ Supported (one webhook target + one config entry per team) |
| Severity → Linear priority + per-severity labels | ✅ Supported, configurable per team |
| Workflow-state selection | ✅ Defaults by state *type* (`unstarted`/`completed`), optional per-team name overrides |
| Idempotency under Endor retries | ✅ Payload-hash ledger |
| Crash recovery without duplicate issues | ✅ Two-phase writes + recovery-footer adoption |
| Deployment | ✅ Docker/Compose (non-root), or bare uvicorn; SQLite or Postgres |
| Local live testing without deployment | ✅ Local `endorctl` scans deliver from the scanning machine (mkcert or tunnel; see DEPLOYMENT.md) |
| Payload replay for iteration | ✅ `tools/replay.py` re-signs and re-sends captured payloads |
| Description truncation for large finding sets | ✅ Above `max_findings_per_issue` (default 50), highest severity first, with a link to Endor |
| Findings with no dependency | ✅ Grouped under a "Findings with no dependencies" sub-issue |

## What is not supported / known limitations

| Item | Notes |
|---|---|
| Bidirectional sync (Linear → Endor) | Out of scope. Closing an issue in Linear does not dismiss the finding in Endor; the next scan does not reopen manually closed issues unless Endor sends an event |
| Aggregation types other than "Dependency across package versions" | The issue model (one sub-issue per dependency) assumes this aggregation |
| Partial resolution | Endor fires no webhook when *some* findings resolve — a sub-issue goes stale until the next new finding or full resolve. Affects every Endor webhook consumer; a nightly reconciliation against the Endor REST API is the documented upgrade path |
| Endor retry exhaustion | Three retries at 1h/2h/4h — an outage beyond ~7h permanently drops events. Alert on availability |
| Horizontal scaling | **Single instance, single worker only** (SQLite + in-process locking). Webhook volume is scan-driven and low; this is not a practical constraint |
| Database loss | The DB is the only notification→issue mapping; losing it means duplicate tickets on the next scan. Back it up (it is tiny). Recovery footers make a manual rebuild via Linear search possible |
| Flapping dependencies | Accumulate closed sub-issues by design (regression = new issue, honest history) |
| Custom templates via the Endor UI | Not possible — the UI has no template fields; templates are installed via the API (DEPLOYMENT.md Part 5) |
| First-class `ACTION_TYPE_LINEAR` in the Endor product | Future product work, out of scope for the bridge |

## Verification status

- **Test suite:** 297 tests — unit coverage for auth/envelope/severity/
  rendering/config, handler coverage against a mocked Linear API (including
  crash-window, adoption, concurrency, and idempotency scenarios), and an
  end-to-end lifecycle test through the real FastAPI app with real HMAC
  signatures.
- **Server-side template validation:** installing the templates via
  `endorctl api update` parses all three through Endor's real template engine
  (its custom functions included) — a broken template cannot be stored.
- **Live verification:** OPEN verified end to end (real scan → real tenant →
  tunnel → bridge → real Linear issues). Outstanding: live UPDATE and RESOLVE
  deliveries, and one agentless/monitored scan to confirm the cloud delivery
  path (both inferred-solid; see DEPLOYMENT.md Part 8).
