# Deploying the Endor Linear Bridge — HOW-TO

A step-by-step deployment guide, written from a live setup against a real Endor
tenant and Linear workspace (2026-07-29). The [README](README.md) explains what
the bridge does and its behavior; this document is the operational runbook:
every command, every Endor-side step, and every failure mode hit along the way.

**Read the ordering warning in [Part 7](#part-7--first-scan-and-verification)
before creating anything on the Endor side.** Endor treats any 4xx from the
bridge as permanent — deliveries sent to a misconfigured bridge are dropped and
never retried. Deploy and verify the bridge *first*, then configure Endor,
then scan.

---

## What you are building

```
endorctl scan ──▶ Endor notification policy ──▶ webhook (HTTPS + HMAC)
                                                      │
                                          tunnel (ngrok / cloudflared)
                                                      │
                                            bridge container :8080
                                                      │
                                              Linear GraphQL API
```

One webhook notification target per Linear team, one action policy per team,
one bridge instance serving all teams.

## Prerequisites

- Docker (with Compose)
- `endorctl` authenticated against your tenant, and `jq` (`brew install jq`)
- A Linear API key with write access to the target team
  (Linear → Settings → API → Personal API keys)
- A way to give the bridge a public HTTPS hostname — see
  [Part 3](#part-3--expose-the-bridge-over-https)

---

## Part 1 — Configure the bridge

All bridge-side work happens in `endor_linear_bridge/`.

```bash
cd endor_linear_bridge
cp config.example.yaml config.yaml
```

Edit `config.yaml`. A working single-team config:

```yaml
linear:
  api_key_env: LINEAR_API_KEY

server:
  inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
  database_url: sqlite:////data/bridge.db     # four slashes: absolute path on the volume

teams:
  cus:                                # <- URL path segment: POST /hooks/cus
    linear_team_key: CUS              # <- your Linear team's key (ENG in ENG-123)
    hmac_secret_env: ENDOR_HMAC_CUS
    labels: [endorlabs]
```

Rules that caused real startup failures when broken:

1. **Delete the example teams you don't use.** Startup resolves *every*
   configured team; a leftover `sec:` block fails with
   `environment variable ENDOR_HMAC_SEC ... is unset or empty`.
2. **`api_key_env` must name the Linear API key variable** — not the bearer
   token. They are different credentials for different directions.
3. **`database_url` needs four slashes** (`sqlite:////data/bridge.db`) so the
   database lands on the mounted volume. With the default (commented-out)
   value the database lives inside the container and dies with it —
   which means duplicate tickets on the next scan.
4. **The team key (`cus:` above) is the URL path segment, not the Linear team
   key.** The webhook URL you register in Endor must end in `/hooks/<that key>`.
   The two names have nothing to do with each other; only `linear_team_key`
   is checked against Linear.

Then create `.env` next to `docker-compose.yml` (Compose reads it
automatically; it is gitignored):

```bash
cat > .env <<EOF
LINEAR_API_KEY=lin_api_...
BRIDGE_BEARER_TOKEN=$(openssl rand -hex 32)
ENDOR_HMAC_CUS=$(openssl rand -hex 32)
EOF
```

`BRIDGE_BEARER_TOKEN` and `ENDOR_HMAC_CUS` are secrets you invent here — Endor
just has to be given the same values in Part 4. Store them in a password
manager; you will paste them into the Endor UI once.

If you renamed the team key or the env var, mirror the change in
`docker-compose.yml`'s `environment:` block — it only passes through the
variables it names.

## Part 2 — Run it

```bash
docker compose up --build
```

Startup is fail-fast and tells you exactly what is wrong (missing env var,
bad API key, unresolvable team key). A healthy start looks like:

```
{"...": "startup complete for teams: cus"}
INFO:  Application startup complete.
```

Verify — the second command is the meaningful one:

```bash
curl http://localhost:8080/healthz   # process is up
curl http://localhost:8080/readyz    # DB reachable + Linear caches loaded
```

A 200 from `/readyz` proves the Linear API key authenticated, the team key
resolved, and labels/workflow states synced. You should also see the
`endorlabs` label appear in the Linear team's settings.

Operational rules (details in the README):

- **One instance, one worker.** Never pass `--workers`.
- **`config.yaml` is read once at startup.** After any config change run
  `docker compose restart` — and re-check the `startup complete for teams:`
  line names the team you expect. A stale config fails in a particularly nasty
  way: see [the 404 trap](#the-404-trap) below.

## Part 3 — Expose the bridge over HTTPS

Endor **rejects any non-`https://` target URL**, and the container speaks
plain HTTP, so something must terminate TLS in front of it. For testing,
tunnels are the fastest option:

| Option | Verdict from testing |
|---|---|
| `cloudflared tunnel --url http://localhost:8080` (quick tunnel, no account) | Works, but the random `trycloudflare.com` hostname **rotates on every restart and can stop resolving without warning** — it died mid-session during this deployment. Fine for a first smoke test only. |
| **ngrok with a free account** (recommended for testing) | One permanent static domain for free: `ngrok http --url=<name>.ngrok-free.app 8080`. Rate limits are irrelevant at webhook volume. |
| Cloudflare **named** tunnel | Free and permanent, but requires a domain you own on Cloudflare. |
| Real deployment | Customer ingress / load balancer terminates TLS as usual. |

A stable hostname matters more than it looks: the hostname is baked into the
notification target, and every change means updating the target — see the
[UI-edit warning](#never-edit-the-target-in-the-ui-after-part-5) first.

Sanity-check the full path before touching Endor:

```bash
curl https://<your-hostname>/healthz   # 200 = internet -> tunnel -> container works
```

Note: for *local* `endorctl` scans only, a tunnel is optional — the README's
mkcert section shows a localhost-TLS alternative (running uvicorn directly,
without Docker). Agentless/monitored scans deliver from Endor's cloud and
always need a public hostname.

## Part 4 — Endor: webhook notification target (UI)

Endor UI → **Integrations → Notifications → Webhook**:

| Field | Value |
|---|---|
| URL endpoint for webhook | `https://<your-hostname>/hooks/cus` — the path segment must match your `config.yaml` team key exactly |
| Auth method | **API Key** — paste the `BRIDGE_BEARER_TOKEN` value |
| Disable HMAC Integration Check | **Leave unchecked.** The bridge requires HMAC; there is no opt-out |
| HMAC Shared Key | paste the `ENDOR_HMAC_CUS` value |
| Custom Headers | none needed |

Save the target, then get its UUID for the next step:

```bash
endorctl api list -r NotificationTarget -n <your-namespace> -o json \
  | jq -r '.list.objects[] | select(.spec.action.webhook_config != null) | "\(.uuid)  \(.spec.action.webhook_config.url.value // .spec.action.webhook_config.url)"'
```

## Part 5 — Endor: custom templates (API only — this step is mandatory)

**The webhook target UI has no custom-template fields.** This is not a missing
step in the dialog — the fields simply are not exposed. Templates live on the
API object at `spec.custom_template.webhook_template`, with one field per
lifecycle operation (`open_action_template`, `update_action_template`,
`resolve_action_template`), and must be set with `endorctl api update`.

Without this step the bridge cannot work at all: the default webhook payload
carries no `event` discriminator, no notification UUID, no project/context
identifiers, and no dependency name — none of the identifiers the bridge's
lifecycle state machine keys on. The three templates in `templates/` exist to
add them.

```bash
cd endor_linear_bridge
set -a; source .env; set +a          # brings ENDOR_HMAC_CUS into the shell

jq -n --rawfile open templates/open.tmpl \
      --rawfile update templates/update.tmpl \
      --rawfile resolve templates/resolve.tmpl \
      --arg url "https://<your-hostname>/hooks/cus" \
      --arg hmac "$ENDOR_HMAC_CUS" \
'{
  spec: {
    action: {
      action_type: "ACTION_TYPE_WEBHOOK",
      webhook_config: { url: $url, hmac_shared_secret: $hmac }
    },
    custom_template: {
      template_type: "CUSTOM_TEMPLATE_TYPE_WEBHOOK",
      webhook_template: {
        open_action_template: $open,
        update_action_template: $update,
        resolve_action_template: $resolve
      }
    }
  }
}' > /tmp/webhook_templates.json

endorctl api update -r NotificationTarget -n <your-namespace> \
  --uuid <TARGET_UUID> \
  --data "$(cat /tmp/webhook_templates.json)" \
  --field-mask spec.custom_template
```

Three non-obvious things about this command, all learned the hard way:

1. **The `spec.action` block is required even though it is not being
   updated.** The API server validates the *incoming* object before applying
   the field mask, and that validation dispatches on the action config —
   omitting it fails with `notification target has no validator defined`.
   The `--field-mask spec.custom_template` ensures only the templates are
   actually written; the URL/HMAC in the payload are read by the validator
   and discarded.
2. **A successful update is also a server-side template validation.** The API
   server parses all three templates with the real webhook plugin's template
   engine (including its custom functions: `jsonEscape`, `packageName`,
   `findingURL`, `increment`). A template syntax error comes back as a
   `FailedPrecondition` naming the problem — it cannot silently store a
   broken template.
3. Verify the templates landed:

```bash
endorctl api get -r NotificationTarget -n <your-namespace> --uuid <TARGET_UUID> -o json \
  | grep -c jsonEscape        # non-zero = templates are on the object
```

### Never edit the target in the UI after Part 5

The UI form does not know `spec.custom_template` exists, so re-saving the
target through the UI may rewrite the spec without it and silently wipe the
templates. Make later changes (e.g. a new tunnel hostname) through the API
instead:

```bash
endorctl api update -r NotificationTarget -n <your-namespace> \
  --uuid <TARGET_UUID> \
  --data '{"spec":{"action":{"action_type":"ACTION_TYPE_WEBHOOK","webhook_config":{"url":"https://<new-hostname>/hooks/cus","hmac_shared_secret":"'"$ENDOR_HMAC_CUS"'"}}}}' \
  --field-mask spec.action.webhook_config.url
```

If someone does save the target from the UI, re-run the `grep -c jsonEscape`
check and re-apply Part 5 if it returns zero.

## Part 6 — Endor: action policy

Endor UI → Policies → create an **action policy**:

- **Action:** Send Notification → the target from Part 4
- **Aggregation:** **Dependency across package versions** — the bridge is
  built for exactly this aggregation; do not pick another
- **Rule conditions:** start with **critical severity only**. This is
  deliberate test design: widening the policy to include high severity later
  is the easiest reliable way to trigger an UPDATE (new findings on the
  *same* dependency)
- **Scope:** tag-scope it to your test project. Team routing lives here, in
  policy scoping — the bridge has no routing logic of its own

## Part 7 — First scan and verification

**Order matters.** The bridge must be up, `/readyz` green, and the startup log
naming the right team *before* the first delivery arrives, because **Endor
treats any 4xx response as permanent** — it marks the delivery unprocessable
and never retries it. During this deployment a scan fired while the container
was still running an older config: every delivery got a 404 and was
permanently dropped. Fixing the bridge and re-scanning was not always enough;
notifications whose open action already failed may need to be deleted in the
Endor UI so a fresh scan recreates them.

Scan a project with a known-vulnerable dependency (in the policy's scope). A
minimal test project:

```bash
mkdir /tmp/bridge-test && cd /tmp/bridge-test && git init
npm init -y && npm install lodash@4.17.4     # several known criticals
endorctl scan --namespace <your-namespace>
```

For a **local** scan, webhook delivery happens from `endorctl` itself at the
end of the scan — instant feedback. **Agentless/monitored** scans deliver from
Endor's cloud on Endor's schedule; both work through the tunnel, but do the
local scan first because failures show up live in your own logs.

Watch the container (`docker compose logs -f bridge`). Success looks like:

```
INFO:  ... "POST /hooks/cus HTTP/1.1" 200 OK
{"message": "created parent issue CUS-123", ...}
{"message": "created sub-issue CUS-124", ...}
```

And in Linear: `[Endor Labs] <project> — main` with a `[Dep] npm://lodash`
sub-issue, priority Urgent, labels `endorlabs` + `endor-critical`.

## Part 8 — Exercising UPDATE and RESOLVE

| Operation | Trigger |
|---|---|
| UPDATE | Widen the policy from critical-only to include high, re-scan. New findings must land on the **same dependency** — adding a different vulnerable package produces a second OPEN instead. Expect a rewritten sub-issue description plus an "N new findings" comment |
| RESOLVE | `npm install lodash@latest`, re-scan. The sub-issue moves to Done with a resolution comment; if it was the parent's last open child, the parent closes too |

Once you have captured a payload, `tools/replay.py` (README, "Replaying a
captured payload") re-fires it with a fresh HMAC signature — no re-scan needed
while iterating.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Startup: `environment variable X ... is unset or empty` | `config.yaml` references a team/env var you didn't provide — usually a leftover example team block. Delete it or set the variable (and pass it through `docker-compose.yml`). |
| Startup: Linear auth or team resolution error | `api_key_env` points at the wrong variable, the API key is invalid, or `linear_team_key` doesn't exist in the workspace. |
| `POST /hooks/... 404` + log `webhook for unknown team key` | URL path segment ≠ `config.yaml` team key — or the container is running a stale config (config loads at startup only; `docker compose restart` and re-check the `startup complete for teams:` line). **These deliveries are permanently dropped by Endor** — see below. |
| `POST /hooks/... 401` + reason `bad_bearer` / `bad_hmac` | Target's API Key ≠ `BRIDGE_BEARER_TOKEN`, or HMAC shared key ≠ the team's `hmac_secret_env` value. Fix the target (via API, not UI) and re-scan. |
| `POST /hooks/... 400` | The delivered payload doesn't parse as the bridge envelope — templates missing (Part 5 skipped) or wrong. Run the `grep -c jsonEscape` check. |
| `endorctl api update` → `notification target has no validator defined` | The `--data` payload lacks the `spec.action` block. See Part 5, point 1. |
| Tunnel hostname stopped resolving | Cloudflare *quick* tunnels are best-effort and die without warning. Switch to an ngrok static domain (free account) and update the target URL via the API. |
| Deliveries arrive, Linear calls fail, bridge returns 503 | Watch the log's Linear error. 503 means Endor **will** retry (1h/2h/4h), so transient Linear problems self-heal. |

### The 404 trap

Worth restating because it cost a full scan cycle: a 4xx from the bridge tells
Endor "unprocessable, do not retry" — correct for genuinely bad requests, but
it means *any* misconfiguration that produces a 4xx (wrong path, wrong bearer,
wrong HMAC, missing templates) permanently consumes every delivery sent while
it lasted. If re-scanning after the fix produces no new delivery, delete the
affected notifications in the Endor UI and scan again.

## Operations

- **Mission Control:** open `http://localhost:8080/dashboard` (or your
  ingress host) for a read-only operator dashboard — health verdict, a
  searchable delivery log with per-delivery traces, per-team wiring, and the
  effective configuration. Every webhook (accepted or rejected) is recorded,
  so a failed delivery shows up here with the step it died on — usually
  faster than grepping the JSON logs. It is **unauthenticated** like
  `/metrics`: keep it off the public tunnel hostname if possible (the tunnel
  only needs to expose `/hooks/*`), or restrict it at the ingress.
- **One instance, one worker** — always (SQLite + in-process locking).
- **Back up `/data/bridge.db`.** It is the only mapping from Endor
  notification UUID to Linear issue; losing it means duplicate tickets on the
  next scan. It is tiny.
- **Upgrading from a root-era volume:** see the README's Docker section for
  the `chown` procedure (mind the Compose volume-name prefix).
- **Metrics:** `/metrics` is unauthenticated — restrict it at the ingress.
  Alert on bridge availability: an outage longer than ~7h (Endor's three
  retries at 1h/2h/4h) permanently drops events.
- **Template updates:** re-run Part 5. The field mask makes it safe to re-apply
  at any time; the server re-validates the templates on every update.
