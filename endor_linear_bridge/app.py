"""FastAPI application: routing, authentication, and error mapping.

The status codes here are load-bearing. Endor treats ANY 4xx as "unprocessable,
do not retry" and surfaces the target as misconfigured
(monorepo pkg/notificationplugins/handlers/webhook/webhook.go:490-493), while
success must be exactly HTTP 200 (webhook.go:431). So 4xx is reserved for auth
and payload problems that a retry cannot fix, and every other failure -- including
unexpected exceptions -- returns 503 so Endor retries at 1h/2h/4h.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response

from endor_linear_bridge import metrics
from endor_linear_bridge.auth import SIGNATURE_HEADER, verify_bearer, verify_hmac
from endor_linear_bridge.config import Config, load_config
from endor_linear_bridge.envelope import EnvelopeError, parse_envelope
from endor_linear_bridge.handlers import HandlerDeps, TransientFailure, handle_event
from endor_linear_bridge.linear_cache import StartupError, build_team_runtimes
from endor_linear_bridge.linear_client import LinearClient
from endor_linear_bridge.models import (
    build_engine,
    build_session_factory,
    create_all,
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


@dataclass
class AppState:
    config: Config
    deps: HandlerDeps | None = None
    ready: bool = False


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
    state = AppState(config=config, deps=deps, ready=deps is not None)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
            logger.info(
                "startup complete for teams: %s", ", ".join(sorted(runtimes))
            )
        yield
        if state.deps is not None and isinstance(state.deps.client, LinearClient):
            await state.deps.client.aclose()

    app = FastAPI(title="Endor Linear Bridge", lifespan=lifespan)
    app.state.bridge = state

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
        return metrics.metrics_response()

    @app.post("/hooks/{team_key}")
    async def receive(team_key: str, request: Request, response: Response):
        # 1. Unknown team -> 404. Checked first: an unknown team has no secret.
        team = state.config.teams.get(team_key)
        if team is None:
            logger.warning("webhook for unknown team key %s", team_key)
            response.status_code = 404
            return {"status": "unknown team"}

        raw_body = await request.body()

        # 2. Bearer token -> 401.
        if not verify_bearer(
            request.headers.get("Authorization"), state.config.inbound_bearer_token
        ):
            logger.warning("bearer token rejected for team %s", team_key)
            metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_bearer").inc()
            response.status_code = 401
            return {"status": "unauthorized"}

        # 3. HMAC over the raw bytes, before parsing -> 401.
        if not verify_hmac(
            raw_body, request.headers.get(SIGNATURE_HEADER), team.hmac_secret
        ):
            logger.warning("HMAC signature rejected for team %s", team_key)
            metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_hmac").inc()
            response.status_code = 401
            return {"status": "unauthorized"}

        # 4. Envelope validation -> 400.
        try:
            envelope = parse_envelope(raw_body)
        except EnvelopeError as exc:
            logger.warning("malformed envelope for team %s: %s", team_key, exc)
            metrics.EVENTS_FAILED.labels(team_key, "unknown", "bad_payload").inc()
            response.status_code = 400
            return {"status": "invalid payload"}

        if state.deps is None:
            logger.error("received webhook before startup completed")
            response.status_code = 503
            return {"status": "not ready"}

        # 5. Process. Anything that goes wrong from here is 503, never 4xx or 500.
        try:
            with metrics.LINEAR_API_LATENCY.time():
                await handle_event(state.deps, team_key, envelope, raw_body)
        except TransientFailure as exc:
            logger.warning(
                "transient failure for %s: %s", envelope.notification.uuid, exc
            )
            metrics.EVENTS_FAILED.labels(
                team_key, envelope.event, "transient"
            ).inc()
            response.status_code = 503
            return {"status": "retry later"}
        except Exception:  # noqa: BLE001 -- a 500 would make Endor stop retrying
            logger.exception(
                "unexpected error processing %s", envelope.notification.uuid
            )
            metrics.EVENTS_FAILED.labels(
                team_key, envelope.event, "unexpected"
            ).inc()
            response.status_code = 503
            return {"status": "retry later"}

        metrics.EVENTS_RECEIVED.labels(team_key, envelope.event).inc()
        return {"status": "ok"}

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
