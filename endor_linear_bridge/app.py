"""FastAPI application: routing, authentication, and error mapping.

The status codes here are load-bearing. Endor treats ANY 4xx as "unprocessable,
do not retry" and surfaces the target as misconfigured
(monorepo pkg/notificationplugins/handlers/webhook/webhook.go:490-493), while
success must be exactly HTTP 200 (webhook.go:431). So 4xx is reserved for auth
and payload problems that a retry cannot fix, and every other failure -- including
unexpected exceptions -- returns 503 so Endor retries at 1h/2h/4h.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from endor_linear_bridge import dashboard, metrics, store, trace
from endor_linear_bridge.auth import SIGNATURE_HEADER, verify_bearer, verify_hmac
from endor_linear_bridge.config import Config, load_config
from endor_linear_bridge.envelope import Envelope, EnvelopeError, parse_envelope
from endor_linear_bridge.handlers import HandlerDeps, TransientFailure, handle_event
from endor_linear_bridge.linear_cache import StartupError, build_team_runtimes
from endor_linear_bridge.linear_client import LinearClient
from endor_linear_bridge.models import (
    ProjectParent,
    build_engine,
    build_session_factory,
    create_all,
    utcnow,
)

logger = logging.getLogger(__name__)

CONFIG_PATH_ENV = "BRIDGE_CONFIG"
DEFAULT_CONFIG_PATH = "config.yaml"

# Fields lifted out of `extra` into top-level JSON keys so log aggregators can
# filter on them directly (spec section 11).
CONTEXT_FIELDS = ("notification_uuid", "team_key", "event", "linear_identifier")


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line, with notification context promoted to keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


_LOGGING_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger. Safe to call twice."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    _LOGGING_CONFIGURED = True


DELIVERY_LOG_RETENTION = timedelta(days=30)
DELIVERY_LOG_PRUNE_INTERVAL_SECONDS = 24 * 60 * 60


@dataclass
class AppState:
    config: Config
    deps: HandlerDeps | None = None
    ready: bool = False
    started_at: datetime | None = None
    synced_at: datetime | None = None


def _derive_linear_action() -> str:
    """Summarize the trace's Linear mutations into the delivery_log column."""
    if trace.has_kind("issue_created"):
        return "created"
    if trace.has_kind("issue_closed"):
        return "closed"
    if any(
        trace.has_kind(kind)
        for kind in ("issue_adopted", "issue_updated", "issue_reopened", "comment_created")
    ):
        return "updated"
    return "none"


def record_delivery_row(
    state: AppState,
    team_key: str,
    envelope: Envelope | None,
    status_code: int,
    failure_reason: str | None,
    started: float,
) -> None:
    """Best-effort append to the delivery log. Runs after the handler resolved,
    so a failure here must never turn a processed webhook into an error."""
    if state.deps is None:
        return

    latency_ms = int((time.monotonic() - started) * 1000)
    trace.step(
        "HTTP response",
        f"{status_code} · {latency_ms} ms",
        ok=status_code < 400,
    )

    if status_code >= 500:
        outcome = "retrying"
    elif status_code >= 400:
        outcome = "rejected"
    elif trace.has_kind("noop"):
        outcome = "noop"
    else:
        outcome = "ok"

    fields: dict[str, object] = {
        "team": team_key,
        "outcome": outcome,
        "status_code": status_code,
        "failure_reason": failure_reason,
        "latency_ms": latency_ms,
        "linear_action": "none",
        "trace": trace.steps(),
    }

    try:
        with state.deps.session_factory() as session:
            if envelope is not None:
                notification = envelope.notification
                fields.update(
                    event_type=envelope.event,
                    notification_uuid=notification.uuid,
                    target=notification.aggregation.target_name,
                    project=notification.project_name,
                    branch=notification.ref_name,
                    findings_new=len(envelope.findings),
                    linear_action=_derive_linear_action(),
                )
                row = store.get_notification(session, notification.uuid)
                if row is not None:
                    fields["linear_identifier"] = row.linear_identifier
                    fields["findings_total"] = len(
                        store.all_findings(session, notification.uuid)
                    )
                    parent = session.get(ProjectParent, row.parent_id)
                    if parent is not None:
                        fields["parent_identifier"] = parent.linear_identifier
            store.record_delivery(session, **fields)
            session.commit()
    except Exception:  # noqa: BLE001 -- observability must not fail the webhook
        logger.exception("failed to write delivery log row")


def metrics_response() -> Response:
    """Render the Prometheus exposition body.

    Lives here rather than in metrics.py so that module can stay free of a
    FastAPI dependency -- linear_client.py imports metrics.py directly to time
    GraphQL requests, and has no business dragging the web framework in.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def readiness_status(state: AppState) -> int:
    """200 once the database and Linear caches are usable, else 503."""
    if not state.ready or state.deps is None:
        return 503
    try:
        with state.deps.session_factory() as session:
            session.connection()
    except Exception:  # noqa: BLE001 -- any DB failure means not ready
        logger.exception("readiness check failed: database unreachable")
        return 503
    return 200


def create_app(config: Config, deps: HandlerDeps | None = None) -> FastAPI:
    """Build the app. Passing `deps` skips startup sync -- used by tests."""
    now = utcnow()
    state = AppState(
        config=config,
        deps=deps,
        ready=deps is not None,
        started_at=now,
        synced_at=now if deps is not None else None,
    )

    async def prune_delivery_log_forever() -> None:
        """Keep the append-only delivery log bounded (spec addendum, section 17)."""
        while True:
            try:
                with state.deps.session_factory() as session:
                    removed = store.prune_delivery_log(
                        session, older_than=utcnow() - DELIVERY_LOG_RETENTION
                    )
                    session.commit()
                if removed:
                    logger.info("pruned %d delivery log rows", removed)
            except Exception:  # noqa: BLE001 -- pruning must never kill the app
                logger.exception("delivery log prune failed")
            await asyncio.sleep(DELIVERY_LOG_PRUNE_INTERVAL_SECONDS)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        prune_task: asyncio.Task | None = None
        if state.deps is None:
            engine = build_engine(config.database_url)
            create_all(engine)
            session_factory = build_session_factory(engine)
            client = LinearClient(
                api_key=config.linear_api_key, api_url=config.linear_api_url
            )
            try:
                runtimes = await build_team_runtimes(client, config)
            except StartupError:
                logger.exception("startup sync with Linear failed")
                await client.aclose()
                raise
            state.deps = HandlerDeps(
                session_factory=session_factory,
                client=client,
                runtimes=runtimes,
                config=config,
            )
            state.ready = True
            state.synced_at = utcnow()
            logger.info(
                "startup complete for teams: %s", ", ".join(sorted(runtimes))
            )
            prune_task = asyncio.create_task(prune_delivery_log_forever())
        yield
        if prune_task is not None:
            prune_task.cancel()
        if state.deps is not None and isinstance(state.deps.client, LinearClient):
            await state.deps.client.aclose()

    app = FastAPI(title="Endor Linear Bridge", lifespan=lifespan)
    app.state.bridge = state

    # Mission Control: read-only dashboard, no auth by deployment decision --
    # restrict at the ingress like /metrics. See dashboard/__init__.py.
    app.include_router(dashboard.build_router(state))
    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(dashboard.STATIC_DIR)),
        name="dashboard-static",
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(response: Response) -> dict[str, str]:
        status = readiness_status(state)
        response.status_code = status
        return {"status": "ok" if status == 200 else "not ready"}

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        if state.deps is not None:
            remaining = getattr(
                state.deps.client, "last_rate_limit_remaining", None
            )
            if remaining is not None:
                metrics.LINEAR_RATE_LIMIT_REMAINING.set(remaining)
        return metrics_response()

    @app.post("/hooks/{team_key}")
    async def receive(team_key: str, request: Request, response: Response):
        started = time.monotonic()
        trace.begin()
        status, body, failure_reason, envelope = await process_webhook(
            team_key, request
        )
        response.status_code = status
        record_delivery_row(state, team_key, envelope, status, failure_reason, started)
        return body

    async def process_webhook(
        team_key: str, request: Request
    ) -> tuple[int, dict[str, str], str | None, Envelope | None]:
        """The webhook pipeline, returning (status, body, failure_reason, envelope).

        Split from the route function so every exit -- rejections included --
        flows back through one delivery-log write.
        """
        # 1. Unknown team -> 404. Checked first: an unknown team has no secret,
        # and this branch needs no request body.
        team = state.config.teams.get(team_key)
        if team is None:
            # The path segment is unauthenticated and attacker-controlled at
            # this point (no team means no secret to verify against), so it
            # must never become a Prometheus label value -- prometheus_client
            # retains one child metric per label tuple forever, and anyone who
            # can reach this public endpoint could grow it without bound by
            # POSTing to a stream of random paths. The real value still goes
            # in the log line, which is bounded by rotation, and in the
            # delivery log, which is bounded by pruning.
            logger.warning(
                "webhook for unknown team key %s",
                team_key,
                extra={"team_key": team_key},
            )
            metrics.EVENTS_FAILED.labels("unknown", "unknown", "unknown_team").inc()
            trace.step("Team lookup", f"no team '{team_key}' configured", ok=False)
            return 404, {"status": "unknown team"}, "unknown_team", None

        # Everything from here down -- including the body read itself, which
        # can raise starlette.requests.ClientDisconnect if the client drops
        # mid-upload -- is covered by the bare `except Exception` below, so a
        # crash anywhere in this block is 503, never the bare 500 Starlette's
        # ServerErrorMiddleware would otherwise produce.
        envelope: Envelope | None = None
        try:
            raw_body = await request.body()

            # 2. Bearer token -> 401.
            if not verify_bearer(
                request.headers.get("Authorization"),
                state.config.inbound_bearer_token,
            ):
                logger.warning(
                    "bearer token rejected for team %s",
                    team_key,
                    extra={"team_key": team_key},
                )
                metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_bearer").inc()
                trace.step(
                    "Bearer token", "rejected before parse", ok=False
                )
                return 401, {"status": "unauthorized"}, "bad_bearer", None

            # 3. HMAC over the raw bytes, before parsing -> 401.
            if not verify_hmac(
                raw_body, request.headers.get(SIGNATURE_HEADER), team.hmac_secret
            ):
                logger.warning(
                    "HMAC signature rejected for team %s",
                    team_key,
                    extra={"team_key": team_key},
                )
                metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_hmac").inc()
                trace.step(
                    "Signature check",
                    "HMAC mismatch — rejected before parse",
                    ok=False,
                )
                return 401, {"status": "unauthorized"}, "bad_hmac", None

            trace.step(
                "Signature verified", "bearer token and HMAC over raw bytes"
            )

            # 4. Envelope validation -> 400.
            try:
                envelope = parse_envelope(raw_body)
            except EnvelopeError as exc:
                logger.warning(
                    "malformed envelope for team %s: %s",
                    team_key,
                    exc,
                    extra={"team_key": team_key},
                )
                metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_payload").inc()
                trace.step("Envelope parse", str(exc), ok=False)
                return 400, {"status": "invalid payload"}, "bad_payload", None

            trace.step(
                "Envelope parsed",
                f"{envelope.event} · {envelope.notification.aggregation.target_name}",
            )

            # This is the earliest point at which both metric labels (team,
            # event) are known for a well-formed, authenticated delivery, so
            # it is where "received" is counted -- including the failures
            # below, so events_failed_total is a true subset and
            # failed/received is a meaningful rate. Counted exactly once: nothing
            # below re-increments it.
            metrics.EVENTS_RECEIVED.labels(team_key, envelope.event).inc()

            if state.deps is None:
                logger.error(
                    "received webhook before startup completed",
                    extra={"team_key": team_key, "event": envelope.event},
                )
                metrics.EVENTS_FAILED.labels(
                    team_key, envelope.event, "not_ready"
                ).inc()
                return 503, {"status": "not ready"}, "not_ready", envelope

            # 5. Process. TransientFailure gets its own reason and log
            # message; anything else -- including an error from Linear that
            # is not a TransientFailure, or one from the body read above --
            # falls through to the bare except below.
            try:
                await handle_event(state.deps, team_key, envelope, raw_body)
            except TransientFailure as exc:
                logger.warning(
                    "transient failure for %s: %s",
                    envelope.notification.uuid,
                    exc,
                    extra={
                        "team_key": team_key,
                        "notification_uuid": envelope.notification.uuid,
                        "event": envelope.event,
                    },
                )
                metrics.EVENTS_FAILED.labels(
                    team_key, envelope.event, "transient"
                ).inc()
                trace.step("Linear call failed", str(exc), ok=False, kind="linear_error")
                return 503, {"status": "retry later"}, "transient", envelope
        except Exception:  # noqa: BLE001 -- a 500 would make Endor stop retrying
            extra = {"team_key": team_key}
            if envelope is not None:
                extra["notification_uuid"] = envelope.notification.uuid
                extra["event"] = envelope.event
            logger.exception(
                "unexpected error processing webhook for team %s",
                team_key,
                extra=extra,
            )
            metrics.EVENTS_FAILED.labels(
                team_key,
                envelope.event if envelope is not None else "unknown",
                "unexpected",
            ).inc()
            trace.step("Unexpected error", "see the service log", ok=False)
            return 503, {"status": "retry later"}, "unexpected", envelope

        return 200, {"status": "ok"}, None, envelope

    return app


def build_default_app() -> FastAPI:
    """Entry point for `uvicorn endor_linear_bridge.app:app`."""
    configure_logging(os.environ.get("BRIDGE_LOG_LEVEL", "INFO"))
    return create_app(load_config(os.environ.get(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH)))


# Module-level app for uvicorn. Constructed lazily so importing this module in
# tests does not require a config file on disk.
def __getattr__(name: str):
    if name == "app":
        return build_default_app()
    raise AttributeError(name)
