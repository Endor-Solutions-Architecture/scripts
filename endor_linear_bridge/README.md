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

## Requirements

- Python 3.12+ (or Docker)
- A Linear API key with write access to the target teams
- One Endor Labs webhook notification target per Linear team

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit. **Secrets never go in this
file** — it names environment variables, and the service resolves them at
startup. A missing or empty variable is a startup failure.

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

### Local

```bash
pip install -r requirements.txt
export LINEAR_API_KEY=lin_api_...
export BRIDGE_BEARER_TOKEN=$(openssl rand -hex 32)
export ENDOR_HMAC_PLAT=$(openssl rand -hex 32)
BRIDGE_CONFIG=config.yaml uvicorn endor_linear_bridge.app:app --port 8080
```

### Docker

```bash
docker compose up --build
```

Set `database_url: sqlite:////data/bridge.db` (four slashes) so the database
lands on the mounted volume.

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
| Custom template | The three documents in `templates/` |

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

```bash
brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1

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

1. **Partial resolution does not fire a webhook.** Endor only sends UPDATE when
   *new* findings appear, so a sub-issue whose findings partly resolve goes stale
   until the next new finding or a full resolve. This affects every Endor webhook
   consumer. A nightly reconciliation job against the Endor REST API is the
   documented upgrade path.
2. **Retry exhaustion.** Three retries at 1h/2h/4h; a longer outage drops events.
3. **The database is the only issue mapping.** See the warning above.
4. **Flapping dependencies accumulate closed sub-issues.** See "How issues are
   structured".

## Development

```bash
pip install -r requirements-dev.txt
pytest endor_linear_bridge/tests -v
```

Module boundaries are enforced by convention and worth preserving: only
`store.py` contains SQL, only `linear_client.py` contains GraphQL, and
`handlers.py` contains neither.
