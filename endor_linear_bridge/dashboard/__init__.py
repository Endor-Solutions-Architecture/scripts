"""Mission Control: the read-only operator dashboard served at /dashboard.

Server-rendered Jinja2 plus a small amount of vanilla JS for the Deliveries
drawer -- no build step, no framework. Everything here READS the state store
and the Prometheus registry; nothing mutates. There are deliberately no retry
or re-sync buttons: recovery happens by re-scanning in Endor or replaying a
captured payload from the CLI.

Served without authentication by explicit deployment decision -- like
/metrics, restrict it at the ingress if the bridge is reachable from
untrusted networks. Secrets are never rendered.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from endor_linear_bridge import metrics, store
from endor_linear_bridge.models import utcnow
from endor_linear_bridge.severity import CRITICAL, HIGH, LOW, MEDIUM, priority_for

if TYPE_CHECKING:  # pragma: no cover -- import cycle guard, typing only
    from endor_linear_bridge.app import AppState

BRIDGE_VERSION = "1.0.0"

PACKAGE_DIR = Path(__file__).parent
STATIC_DIR = PACKAGE_DIR / "static"

WINDOWS: dict[str, tuple[timedelta, str]] = {
    "24h": (timedelta(hours=24), "Last 24h"),
    "7d": (timedelta(days=7), "Last 7 days"),
    "30d": (timedelta(days=30), "Last 30 days"),
}
DEFAULT_WINDOW = "24h"
VOLUME_BUCKETS = 12

SEVERITY_ROWS = (
    (CRITICAL, "Critical", "critical"),
    (HIGH, "High", "high"),
    (MEDIUM, "Medium", "medium"),
    (LOW, "Low", "low"),
)

# Failure classes shown on the Overview panel, in display order. The reasons
# are the bridge's real events_failed_total reasons, not invented categories.
FAILURE_CLASSES = (
    ("transient", "Linear or database unavailable · Endor retries 1h / 2h / 4h", "RETRYING", "warning"),
    ("unexpected", "Unexpected error · returned 503 so Endor retries", "RETRYING", "warning"),
    ("bad_hmac", "HMAC mismatch · rejected before parse", "DROPPED", "danger"),
    ("bad_bearer", "Bearer token rejected · rejected before parse", "DROPPED", "danger"),
    ("bad_payload", "Malformed envelope · template error", "DROPPED", "danger"),
    ("unknown_team", "POST to a team route that is not configured", "DROPPED", "danger"),
)

templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite hands naive datetimes back; they were written as UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _ago(dt: datetime | None) -> str:
    dt = _aware(dt)
    if dt is None:
        return "never"
    seconds = max(0, int((utcnow() - dt).total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _uptime(started_at: datetime | None) -> str:
    started_at = _aware(started_at)
    if started_at is None:
        return "—"
    seconds = max(0, int((utcnow() - started_at).total_seconds()))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"up {days}d {hours:02d}h"
    if hours:
        return f"up {hours}h {minutes:02d}m"
    return f"up {minutes}m"


def _histogram_quantile(histogram, quantile: float) -> float | None:
    """Approximate a quantile (in seconds) from cumulative bucket counts."""
    buckets: list[tuple[float, float]] = []
    total = 0.0
    for family in histogram.collect():
        for sample in family.samples:
            if sample.name.endswith("_bucket"):
                le = sample.labels.get("le", "+Inf")
                bound = float("inf") if le == "+Inf" else float(le)
                buckets.append((bound, sample.value))
            elif sample.name.endswith("_count"):
                total = sample.value
    if total == 0:
        return None
    threshold = quantile * total
    for bound, cumulative in sorted(buckets):
        if cumulative >= threshold:
            return None if bound == float("inf") else bound
    return None


def _latency_ms(quantile: float) -> str:
    value = _histogram_quantile(metrics.LINEAR_API_LATENCY, quantile)
    if value is None:
        return "—"
    return f"{int(value * 1000)}ms"


def _sqlite_path(database_url: str) -> str | None:
    if not database_url.startswith("sqlite"):
        return None
    path = database_url.split("///", 1)[-1]
    return path if path and path != ":memory:" else None


def _store_line(database_url: str) -> str:
    path = _sqlite_path(database_url)
    if path is None:
        return database_url.split(":", 1)[0]
    line = "sqlite · WAL"
    try:
        size = os.path.getsize(path)
        line += f" · {size / (1024 * 1024):.1f} MB"
    except OSError:
        pass
    return line


def _window(param: str | None) -> tuple[str, timedelta, str]:
    key = param if param in WINDOWS else DEFAULT_WINDOW
    delta, label = WINDOWS[key]
    return key, delta, label


def _sidebar(state: AppState, active: str) -> dict[str, Any]:
    return {
        "active": active,
        "ready": state.ready,
        "version": BRIDGE_VERSION,
        "uptime": _uptime(state.started_at),
        "store_line": _store_line(state.config.database_url),
        "synced_at": _aware(state.synced_at),
    }


def _severity_bars(counts: dict[str, int]) -> list[dict[str, Any]]:
    rows = []
    peak = max([counts.get(sev, 0) for sev, _, _ in SEVERITY_ROWS] + [1])
    for severity, label, css in SEVERITY_ROWS:
        count = counts.get(severity, 0)
        rows.append(
            {"label": label, "css": css, "count": count,
             "pct": round(100 * count / peak) if count else 0}
        )
    return rows


def _volume_buckets(
    events: list[tuple[datetime, str]], since: datetime, delta: timedelta
) -> list[dict[str, int]]:
    """Stack (open, update, resolve) counts into fixed-width time buckets."""
    buckets = [
        {"open": 0, "update": 0, "resolve": 0} for _ in range(VOLUME_BUCKETS)
    ]
    span = delta.total_seconds()
    since = _aware(since)
    for at, event in events:
        at = _aware(at)
        offset = (at - since).total_seconds()
        index = min(int(offset / span * VOLUME_BUCKETS), VOLUME_BUCKETS - 1)
        if event in buckets[index]:
            buckets[index][event] += 1
    peak = max([sum(b.values()) for b in buckets] + [1])
    for bucket in buckets:
        for event in ("open", "update", "resolve"):
            bucket[f"{event}_pct"] = round(100 * bucket[event] / peak)
    return buckets


RESULT_WORDS = {"ok": "ok", "noop": "no-op", "retrying": "retrying", "rejected": "rejected"}


def _delivery_row(delivery, mix: dict[str, dict[str, int]]) -> dict[str, Any]:
    received = _aware(delivery.received_at)
    findings = "—"
    if delivery.findings_new is not None:
        findings = f"{delivery.findings_new} new"
        if delivery.findings_total is not None:
            findings += f" · {delivery.findings_total} stored"

    severity_counts = mix.get(delivery.notification_uuid or "", {})
    priority = None
    for severity, _, _ in SEVERITY_ROWS:  # ordered most severe first
        if severity_counts.get(severity):
            priority = priority_for(severity)
            break

    return {
        "id": delivery.id,
        "time": received.strftime("%H:%M:%S") if received else "—",
        "ago": _ago(delivery.received_at),
        "event": delivery.event_type or "—",
        "team": delivery.team,
        "target": delivery.target or "rejected before parse",
        "project_branch": (
            f"{delivery.project} · {delivery.branch}" if delivery.project else ""
        ),
        "findings": findings,
        "linear": delivery.linear_identifier or "no call made",
        "has_linear": delivery.linear_identifier is not None,
        "latency": f"{delivery.latency_ms}ms" if delivery.latency_ms is not None else "—",
        "result_ok": delivery.status_code < 400,
        "result": f"{delivery.status_code} {RESULT_WORDS.get(delivery.outcome, delivery.outcome)}",
        "outcome": delivery.outcome,
        "drawer": {
            "target": delivery.target or "Rejected before parse",
            "subtitle": " · ".join(
                part
                for part in (
                    delivery.event_type,
                    received.strftime("%H:%M:%S UTC") if received else None,
                    delivery.project,
                )
                if part
            ),
            "notification_uuid": delivery.notification_uuid or "—",
            "linear": delivery.linear_identifier or "no call made",
            "parent": delivery.parent_identifier or "—",
            "findings_stored": delivery.findings_total,
            "steps": delivery.trace or [],
            "severity": _severity_bars(severity_counts),
            "priority": priority,
        },
    }


def _delivery_rows(session, deliveries) -> list[dict[str, Any]]:
    uuids = [d.notification_uuid for d in deliveries if d.notification_uuid]
    mix = store.severity_mix(session, uuids)
    return [_delivery_row(d, mix) for d in deliveries]


def _status_read(ready: bool, summary: dict[str, int], reasons: dict[str, int]) -> tuple[str, str, str]:
    """(verdict, css class, plain-language sentence) for the Overview status bar."""
    if not ready:
        return (
            "Not ready",
            "danger",
            "Startup has not completed — the Linear cache or the database is "
            "not usable yet. Check /readyz and the service log.",
        )

    parts: list[str] = []
    if summary["retrying"]:
        n = summary["retrying"]
        parts.append(
            f"{n} deliver{'y is' if n == 1 else 'ies are'} mid-retry and will "
            "land on their own"
        )
    rejected_bits = []
    auth_rejections = reasons.get("bad_hmac", 0) + reasons.get("bad_bearer", 0)
    if auth_rejections:
        rejected_bits.append(
            f"{auth_rejections} rejected at the signature or bearer check — "
            "fix the secret and re-scan"
        )
    other_rejections = reasons.get("bad_payload", 0) + reasons.get("unknown_team", 0)
    if other_rejections:
        rejected_bits.append(
            f"{other_rejections} rejected as unprocessable — check the "
            "template and the route"
        )
    parts.extend(rejected_bits)

    if not parts:
        return (
            "Operational",
            "ok",
            "Ingest, HMAC, database and Linear are all healthy. Nothing is "
            "mid-retry and nothing was rejected in this window.",
        )
    verdict = "Degraded" if rejected_bits else "Recovering"
    return verdict, "warning", "Ingest, database and Linear are up. " + "; ".join(parts) + "."


def build_router(state: AppState) -> APIRouter:
    router = APIRouter()

    def base_context(request: Request, active: str, title: str, subtitle: str):
        return {
            "request": request,
            "sidebar": _sidebar(state, active),
            "title": title,
            "subtitle": subtitle,
        }

    @router.get("/dashboard", response_class=HTMLResponse)
    async def overview(request: Request, window: str | None = None):
        window_key, delta, window_label = _window(window)
        since = utcnow() - delta

        with state.deps.session_factory() as session:
            summary = store.delivery_summary(session, since=since)
            reasons = store.failure_counts(session, since=since)
            team_stats = store.team_delivery_stats(session, since=since)
            issues = store.issue_counts(session)
            severities = store.severity_totals(session)
            total_findings = store.findings_total(session)
            events = store.event_times(session, since=since)
            recent = _delivery_rows(
                session, store.recent_deliveries(session, since=None, limit=5)
            )

        verdict, verdict_css, sentence = _status_read(state.ready, summary, reasons)
        event_totals = {
            kind: sum(1 for _, e in events if e == kind)
            for kind in ("open", "update", "resolve")
        }
        issues_open = sum(c["open"] for c in issues.values())
        issues_closed = sum(c["closed"] for c in issues.values())
        failures = summary["retrying"] + summary["rejected"]

        rate_remaining = getattr(state.deps.client, "last_rate_limit_remaining", None)

        teams = []
        for key in sorted(state.config.teams):
            stats = team_stats.get(
                key, {"open": 0, "update": 0, "resolve": 0, "failed": 0, "last_event_at": None}
            )
            counts = issues.get(key, {"open": 0, "closed": 0})
            teams.append(
                {
                    "key": key,
                    **{k: stats[k] for k in ("open", "update", "resolve", "failed")},
                    "issues": f"{counts['open']} open · {counts['closed']} closed",
                    "last_event": _ago(stats["last_event_at"]),
                }
            )

        failure_rows = [
            {"reason": reason, "detail": detail, "status": status_word if reasons.get(reason) else "CLEAR",
             "css": css if reasons.get(reason) else "muted", "count": reasons.get(reason, 0)}
            for reason, detail, status_word, css in FAILURE_CLASSES
        ]

        context = base_context(
            request,
            "overview",
            "Mission control",
            "Endor notifications → Linear issues · teams "
            + ", ".join(sorted(state.config.teams)),
        )
        context.update(
            window=window_key,
            window_label=window_label,
            verdict=verdict,
            verdict_css=verdict_css,
            sentence=sentence,
            last_delivery=_ago(None) if not recent else recent[0]["ago"],
            events_total=summary["received"],
            event_totals=event_totals,
            findings_total=total_findings,
            issues_open=issues_open,
            issues_closed=issues_closed,
            failures=failures,
            retrying=summary["retrying"],
            rejected=summary["rejected"],
            p95=_latency_ms(0.95),
            rate_remaining=rate_remaining,
            buckets=_volume_buckets(events, since, delta),
            severity_bars=_severity_bars(severities),
            teams=teams,
            failure_rows=failure_rows,
            recent=recent,
        )
        return templates.TemplateResponse(request, "overview.html", context)

    @router.get("/dashboard/deliveries", response_class=HTMLResponse)
    async def deliveries(
        request: Request,
        window: str | None = None,
        filter: str = "all",
        q: str | None = None,
    ):
        window_key, delta, window_label = _window(window)
        since = utcnow() - delta

        event_type = filter if filter in ("open", "update", "resolve") else None
        failed_only = filter == "failed"

        with state.deps.session_factory() as session:
            summary = store.delivery_summary(session, since=since)
            rows = _delivery_rows(
                session,
                store.recent_deliveries(
                    session,
                    since=since,
                    event_type=event_type,
                    failed_only=failed_only,
                    search=q,
                ),
            )

        context = base_context(
            request,
            "deliveries",
            "Deliveries",
            "Every webhook the bridge accepted or rejected · read-only",
        )
        context.update(
            window=window_key,
            window_label=window_label,
            filter=filter,
            q=q or "",
            summary=summary,
            rows=rows,
            drawer_data={str(row["id"]): row["drawer"] for row in rows},
        )
        return templates.TemplateResponse(request, "deliveries.html", context)

    @router.get("/dashboard/teams", response_class=HTMLResponse)
    async def teams(request: Request):
        since = utcnow() - timedelta(hours=24)
        with state.deps.session_factory() as session:
            team_stats = store.team_delivery_stats(session, since=since)
            issues = store.issue_counts(session)

        cards = []
        for key in sorted(state.config.teams):
            team_config = state.config.teams[key]
            runtime = (state.deps.runtimes or {}).get(key)
            stats = team_stats.get(
                key, {"open": 0, "update": 0, "resolve": 0, "failed": 0, "last_event_at": None}
            )
            counts = issues.get(key, {"open": 0, "closed": 0})
            states = []
            severity_chips = []
            if runtime is not None:
                states = [
                    {"name": team_config.open_state or "default unstarted",
                     "role": "open", "id": runtime.open_state_id},
                    {"name": team_config.close_state or "default completed",
                     "role": "close", "id": runtime.close_state_id},
                    {"name": team_config.reopen_state or "same as open",
                     "role": "reopen", "id": runtime.reopen_state_id},
                ]
                severity_chips = [
                    {"name": f"{team_config.severity_label_prefix}{word}", "css": word}
                    for word in ("critical", "high", "medium", "low")
                    if word in runtime.severity_label_ids
                ]
            events_24h = stats["open"] + stats["update"] + stats["resolve"]
            cards.append(
                {
                    "key": key,
                    "linear_team": team_config.linear_team_key,
                    "route": f"POST /hooks/{key}",
                    "hmac": "present",
                    "synced": _aware(state.synced_at),
                    "failed": stats["failed"],
                    "states": states,
                    "severity_chips": severity_chips,
                    "labels": ", ".join(team_config.labels) or "—",
                    "volume": (
                        f"{events_24h} events · {stats['open']} open / "
                        f"{stats['update']} update / {stats['resolve']} resolve"
                    ),
                    "issues": f"{counts['open']} open · {counts['closed']} closed",
                    "last_event": _ago(stats["last_event_at"]),
                }
            )

        context = base_context(
            request,
            "teams",
            "Teams",
            "Route, secret, and the Linear state and label ids resolved at startup",
        )
        context.update(cards=cards, ready=state.ready)
        return templates.TemplateResponse(request, "teams.html", context)

    @router.get("/dashboard/config", response_class=HTMLResponse)
    async def config_page(request: Request):
        config = state.config
        team_keys = ", ".join(sorted(config.teams))
        rate_remaining = getattr(state.deps.client, "last_rate_limit_remaining", None)
        log_level = logging.getLevelName(logging.getLogger().level)

        groups = [
            {
                "title": "Runtime",
                "icon": "memory",
                "rows": [
                    ("Version", f"bridge v{BRIDGE_VERSION}", ""),
                    ("Uptime", _uptime(state.started_at), ""),
                    ("Store", _store_line(config.database_url), ""),
                    ("Log level", log_level, ""),
                    ("Worker model", "single process · single instance (mandated by SQLite and in-process locks)", "secondary"),
                ],
            },
            {
                "title": "Endpoints",
                "icon": "api",
                "rows": [
                    ("POST /hooks/{team}", f"webhook ingest · HMAC over raw bytes · teams: {team_keys}", "accent"),
                    ("GET /healthz", "liveness · no dependency checks", "accent"),
                    ("GET /readyz", "readiness · startup sync complete and database reachable", "accent"),
                    ("GET /metrics", "Prometheus exposition · unauthenticated, restrict at ingress", "accent"),
                    ("GET /dashboard", "this dashboard · read-only · unauthenticated, restrict at ingress", "accent"),
                ],
            },
            {
                "title": "Behaviour",
                "icon": "tune",
                "rows": [
                    ("max_findings_per_issue", f"{config.max_findings_per_issue} · descriptions truncate with a count line", ""),
                    ("Dedupe", "payload-hash ledger · an identical redelivery is a no-op", "secondary"),
                    ("Finding union", "findings accumulate per notification · resolve keeps history", "secondary"),
                    ("Priority", "derived from max severity across the stored union", "secondary"),
                    ("No-deps sentinel", "__ENDOR_FINDINGS_WITH_NO_DEPS__ → “Findings with no dependencies”", "secondary"),
                    ("Parent strategy", "one parent issue per project + branch + team, created on demand", "secondary"),
                ],
            },
            {
                "title": "Failure semantics",
                "icon": "shield",
                "rows": [
                    ("401 · auth", "bearer or HMAC rejected before parse · Endor will not retry", "danger"),
                    ("400 · unprocessable", "malformed envelope · no retry", "danger"),
                    ("503 · dependency down", "Linear or database unavailable · Endor retries 1h / 2h / 4h", "warning"),
                    ("Linear 429", "in-process backoff, then 503 to hand the retry back to Endor", "warning"),
                    ("Pending rows", "written before any Linear call · adopted on the next delivery", "cyan"),
                ],
            },
            {
                "title": "Linear API",
                "icon": "bolt",
                "rows": [
                    ("Rate limit", f"{rate_remaining} remaining" if rate_remaining is not None else "no request made yet", ""),
                    ("Latency", f"p50 {_latency_ms(0.5)} · p95 {_latency_ms(0.95)} · p99 {_latency_ms(0.99)}", ""),
                    ("API URL", config.linear_api_url, "secondary"),
                    ("Team cache", "resolved at startup · immutable until restart", "secondary"),
                ],
            },
        ]

        context = base_context(
            request,
            "config",
            "Configuration",
            "Effective values in the running process · secrets never shown",
        )
        context.update(groups=groups)
        return templates.TemplateResponse(request, "config.html", context)

    return router
