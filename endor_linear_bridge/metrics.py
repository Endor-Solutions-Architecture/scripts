"""Prometheus metrics for the bridge.

Kept free of framework imports (prometheus_client only). linear_client.py
imports this module directly to time GraphQL requests, and that module has no
business depending on FastAPI -- so the `/metrics` response helper, which does
need FastAPI's Response, lives in app.py instead of here.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

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
