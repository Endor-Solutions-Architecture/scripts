# Endor Linear Bridge

Receives Endor Labs webhook notifications and maintains Linear issues: one
**parent issue per project/context/team** and one **sub-issue per dependency**
with findings. Handles the full lifecycle — create on open, comment and rewrite
on update, close on resolve.

Endor Labs ships first-class ticketing integrations for Jira and Azure DevOps
Boards but not Linear. This service fills that gap with no product changes.

## How issues are structured

```
[Endor Labs] webapp — main            <- parent, one per project + context + team
 ├─ [Dep] npm://lodash                <- sub-issue, one per dependency
 ├─ [Dep] npm://axios
 └─ Findings with no dependencies     <- the __ENDOR_FINDINGS_WITH_NO_DEPS__ group
```

- The parent closes automatically when its last sub-issue resolves, and reopens
  if new findings arrive later.
- **A dependency that is fixed and later regresses gets a new sub-issue**, not a
  reopened one. Endor issues a new notification UUID for the regression and the
  old sub-issue is already closed, so a chronically flapping dependency
  accumulates closed siblings. This is intentional — the history stays honest.
- Descriptions truncate above `max_findings_per_issue` (default 50) with a link
  back to Endor Labs.

### Severity to Linear priority

| Endor severity | Linear priority |
|---|---|
| Critical | 1 (Urgent) |
| High | 2 (High) |
| Medium | 3 (Medium) |
| Low | 4 (Low) |
| Anything else / unrecognized | 0 (No priority) |

Set `priority_from_severity: false` on a team to force every issue to 0
(no priority) regardless of finding severity.

## Requirements

- Python 3.12+ (or Docker)
- A Linear API key with write access to the target teams
- One Endor Labs webhook notification target per Linear team

## Configuration

Copy `endor_linear_bridge/config.example.yaml` to `endor_linear_bridge/config.yaml`
and edit — both the local and Docker instructions below expect it there.
**Secrets never go in this file** — it names environment variables, and the
service resolves them at startup. A missing or empty variable is a startup
failure.

```yaml
linear:
  api_key_env: LINEAR_API_KEY
server:
  inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
  database_url: sqlite:///./bridge.db
teams:
  plat:                              # receives POST /hooks/plat
    linear_team_key: PLAT
    hmac_secret_env: ENDOR_HMAC_PLAT
    labels: [endorlabs]
```

Every option is documented inline in `config.example.yaml`. For Postgres, set
`database_url: postgresql+psycopg://user:pass@host/db` and also install
`psycopg[binary]>=3.2.0`, which is not in `requirements.txt` because SQLite is
the default.

### Adding a Linear team

One new webhook target + one new scoped action policy in Endor + one entry under
`teams:`. No code changes.

## Running

All commands in this section run from the **repository root** — the directory
that contains `endor_linear_bridge/` — except the Docker commands, which run
from inside `endor_linear_bridge/` where `docker-compose.yml` lives.

> **Run exactly one instance, with one worker process.** SQLite requires it
> (a second writer hits lock contention), and issue creation is serialized
> per project through an in-process lock, which multiple processes would
> defeat — two workers handling overlapping deliveries could each create a
> parent issue. Do not pass `--workers` to uvicorn. Webhook volume is
> scan-driven and low; one worker is not a bottleneck.

### Local

```bash
pip install -r endor_linear_bridge/requirements.txt
export LINEAR_API_KEY=lin_api_...
export BRIDGE_BEARER_TOKEN=$(openssl rand -hex 32)
export ENDOR_HMAC_PLAT=$(openssl rand -hex 32)
BRIDGE_CONFIG=endor_linear_bridge/config.yaml uvicorn endor_linear_bridge.app:app --port 8080
```

### Docker

```bash
cd endor_linear_bridge
docker compose up --build
```

Set `database_url: sqlite:////data/bridge.db` (four slashes) so the database
lands on the mounted volume.

The container runs as a non-root user (the environment holds the Linear API
key and every team's HMAC secret). The Dockerfile `chown`s `/data` to that
user at build time, which Docker applies when it initializes a fresh named
volume (as `docker-compose.yml`'s `bridge-data` volume is) from the image's
directory contents — a bind-mounted host directory is not affected and should
already be writable by uid `10001`, or by anyone if that is acceptable in your
environment.

**Upgrading a deployment that previously ran as root:** a named volume
populated by an older root-running container keeps its root ownership, and the
non-root container will fail with permission errors on startup. Before the
first deployment on such a volume, change its ownership to the container's
user. Note that Compose prefixes the volume name with the project name —
find the real name with `docker volume ls` (with this directory layout it is
`endor_linear_bridge_bridge-data`), then:

```bash
docker run --rm -v endor_linear_bridge_bridge-data:/data alpine chown -R 10001:10001 /data
```

Fresh volumes need nothing.

> **The database is the only mapping from Endor notification UUID to Linear
> issue.** Losing it orphans open tickets and the next scan creates duplicates.
> Back it up, and never run on an ephemeral filesystem without pointing
> `database_url` at Postgres. Every issue description carries an
> `Endor-notification-uuid:` footer, so a rebuild via Linear search is possible
> but manual.

## Endor Labs setup

For each Linear team — example team key `PLAT`:

**1. Webhook notification target** (Integrations → Notifications → Webhook)

| Field | Value |
|---|---|
| URL | `https://<bridge-host>/hooks/plat` — **must be https**, Endor rejects plain http |
| Auth method | **API Key**, value = `BRIDGE_BEARER_TOKEN` |
| HMAC | **Enabled**, secret = `ENDOR_HMAC_PLAT`. Required — the bridge has no opt-out |
| Custom template | **Three separate fields, one per lifecycle operation** — `templates/open.tmpl` → the target's *Open action* template, `templates/update.tmpl` → its *Update action* template, `templates/resolve.tmpl` → its *Resolve action* template. **⚠ Unconfirmed against the live tenant UI — verify the exact field names on first setup** (see "Known limitations" below). **Failure mode if this is wrong:** pasting the same template (e.g. `open.tmpl`) into all three fields yields a bridge that creates issues and never closes them — a silent failure that looks fine until the first dependency is actually fixed. |

**2. Action policy**

- Action: **Send Notification** → that team's webhook target
- Aggregation type: **Dependency across package versions**
- Scope: project tags identifying the team's repos (e.g. `team=platform`).
  **Team routing lives here**, in policy scoping — not in the bridge.
- Rule conditions: severity thresholds to taste

## Endpoints

| Route | Purpose |
|---|---|
| `POST /hooks/{team_key}` | Webhook receiver |
| `GET /healthz` | Liveness |
| `GET /readyz` | Readiness — database reachable and Linear caches loaded |
| `GET /metrics` | Prometheus exposition |

`/metrics` is **unauthenticated** and exposes every configured team key as a
label value — restrict it at the ingress (internal network / scrape-only
allowlist) rather than exposing it alongside `/hooks/{team_key}`.

`events_received_total{team,event}` counts arrivals (incremented once the
delivery is authenticated and its envelope parses, before Linear is called),
and `events_failed_total{team,event,reason}` counts a subset of those that
then failed — so `failed / received` is a meaningful failure rate. The
`team` label on `events_failed_total`'s `unknown_team` reason is always the
literal string `unknown`, never the requested path segment, since that
segment is unauthenticated and would otherwise let anyone grow the metric's
cardinality without bound.

### Response codes, and why they matter

Endor treats **any 4xx as permanent** — it stops retrying and flags the target
as misconfigured. So 4xx is reserved for problems a retry cannot fix:

| Code | Meaning | Endor's behavior |
|---|---|---|
| 200 | Processed | Success — the only accepted success code |
| 400 | Malformed payload | No retry; check the custom templates |
| 401 | Bad bearer or HMAC | No retry; check the target's auth config |
| 404 | Unknown team key | No retry; check the URL path against `teams:` |
| 503 | Linear unavailable, DB down, or an unexpected error | Retries at 1h / 2h / 4h |

Endor retries a maximum of 3 times, so an outage longer than about 7 hours can
permanently drop an event. Alert on availability.

## Testing against real Endor without deploying

Webhook delivery originates from **`endorctl`**, not Endor's cloud — the webhook
plugin executes in-process in the scanning binary. So a bridge on your laptop
receives real webhooks from a local scan. The only constraint is that Endor
requires an `https://` URL, which `mkcert` satisfies by installing a locally
trusted CA:

Run these from the repository root, so the generated certificate files land
next to where the `uvicorn` command below expects them:

```bash
brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1
# writes ./localhost+1.pem and ./localhost+1-key.pem in the current directory

uvicorn endor_linear_bridge.app:app --host 127.0.0.1 --port 8443 \
  --ssl-certfile localhost+1.pem --ssl-keyfile localhost+1-key.pem
```

Point the notification target at `https://localhost:8443/hooks/plat` and run
`endorctl scan`.

Triggering each operation:

| Operation | Trigger |
|---|---|
| OPEN | Scan a project with a vulnerable dependency for the first time |
| UPDATE | Requires **new findings on the same dependency**. Easiest: start with a critical-only policy, scan, then widen it to include high severity and re-scan. Adding a *different* vulnerable dependency produces a second OPEN, not an UPDATE |
| RESOLVE | Bump the dependency to a fixed version and re-scan |

**Monitored and scheduled scans run in Endor's cloud**, so those deliveries do
need a publicly reachable endpoint — a `cloudflared` tunnel to localhost is the
cheapest way to test that path.

### Replaying a captured payload

Run from the repository root, like the commands above. `--payload` is resolved
relative to your current directory, so if `captured.json` was saved elsewhere,
give a root-relative (or absolute) path to it:

```bash
python -m endor_linear_bridge.tools.replay \
  --url https://localhost:8443/hooks/plat \
  --payload captured.json \
  --bearer "$BRIDGE_BEARER_TOKEN" \
  --secret "$ENDOR_HMAC_PLAT"
```

Redelivering identical bytes is a no-op by design — the idempotency ledger keys
on (notification uuid, event, payload hash). Edit a field to make it a new event.

## Known limitations

0. **Highest priority to confirm during first live setup: the custom template
   → action field mapping.** The Endor setup table above documents
   `open.tmpl` / `update.tmpl` / `resolve.tmpl` going into three separate
   per-operation template fields (Open / Update / Resolve action templates),
   but this has not been verified against a live tenant's UI — the exact
   field names are inferred, not confirmed. Get this wrong (e.g. the same
   template pasted into all three) and the bridge creates issues but never
   closes them, silently, until someone notices a "resolved" dependency still
   has an open ticket. Confirm this first, before anything else, on the first
   live setup.
1. **Partial resolution does not fire a webhook.** Endor only sends UPDATE when
   *new* findings appear, so a sub-issue whose findings partly resolve goes stale
   until the next new finding or a full resolve. This affects every Endor webhook
   consumer. A nightly reconciliation job against the Endor REST API is the
   documented upgrade path.
2. **Retry exhaustion.** Three retries at 1h/2h/4h; a longer outage drops
   events. One extra consequence of crash-safe issue creation: an OPEN that
   fails on every retry leaves a permanent `pending` row with no Linear
   issue, which counts as an unresolved child and keeps its parent issue from
   auto-closing. If a parent stays open with no visible open sub-issues,
   delete the stale `pending` rows from `notification_issues`.
3. **The database is the only issue mapping.** See the warning above.
4. **Flapping dependencies accumulate closed sub-issues.** See "How issues are
   structured".

## Development

Run from the repository root:

```bash
pip install -r endor_linear_bridge/requirements-dev.txt
pytest endor_linear_bridge/tests -v
```

Module boundaries are enforced by convention and worth preserving: only
`store.py` contains SQL, only `linear_client.py` contains GraphQL, and
`handlers.py` contains neither.
