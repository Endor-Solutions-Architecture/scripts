"""Prometheus metrics for the bridge."""

from __future__ import annotations

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram
from prometheus_client import generate_latest

EVENTS_RECEIVED = Counter(
    "events_received_total",
    "Webhook events accepted and processed",
    ["team", "event"],
)

EVENTS_FAILED = Counter(
    "events_failed_total",
    "Webhook events that could not be processed",
    ["team", "event", "reason"],
)

LINEAR_API_LATENCY = Histogram(
    "linear_api_latency_seconds",
    "Latency of Linear GraphQL requests",
)

LINEAR_RATE_LIMIT_REMAINING = Gauge(
    "linear_rate_limit_remaining",
    "Requests remaining in the current Linear rate-limit window",
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
