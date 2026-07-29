"""Every webhook the bridge accepts or rejects leaves a delivery_log row."""

import pytest
from fastapi.testclient import TestClient

from endor_linear_bridge import store
from endor_linear_bridge.app import create_app
from endor_linear_bridge.handlers import HandlerDeps
from endor_linear_bridge.linear_client import LinearTransientError
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_app import post
from endor_linear_bridge.tests.test_handlers_open import (
    CONFIG,
    RUNTIME,
    envelope_body,
)


@pytest.fixture
def client(session_factory):
    deps = HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )
    with TestClient(create_app(CONFIG, deps=deps)) as test_client:
        test_client.deps = deps
        yield test_client


def rows(client):
    with client.deps.session_factory() as session:
        return store.recent_deliveries(session, since=None)


def test_successful_open_writes_a_complete_row(client):
    response = post(client, envelope_body())
    assert response.status_code == 200

    (row,) = rows(client)
    assert row.team == "plat"
    assert row.event_type == "open"
    assert row.notification_uuid == "notif-1"
    assert row.target == "npm://lodash"
    assert row.project == "webapp"
    assert row.branch == "main"
    assert row.outcome == "ok"
    assert row.status_code == 200
    assert row.failure_reason is None
    assert row.findings_new == 1
    assert row.findings_total == 1
    assert row.linear_action == "created"
    assert row.linear_identifier and row.linear_identifier.startswith("PLAT-")
    assert row.parent_identifier and row.parent_identifier.startswith("PLAT-")
    assert row.latency_ms is not None
    steps = [s["step"] for s in row.trace]
    assert "Signature verified" in steps
    assert steps[-1] == "HTTP response"


def test_hmac_rejection_writes_a_row_with_no_parsed_fields(client):
    response = post(client, envelope_body(), secret="wrong")
    assert response.status_code == 401

    (row,) = rows(client)
    assert row.outcome == "rejected"
    assert row.failure_reason == "bad_hmac"
    assert row.status_code == 401
    assert row.notification_uuid is None
    assert row.target is None
    assert row.linear_action == "none"
    assert any(not s["ok"] for s in row.trace)


def test_bearer_rejection_is_recorded(client):
    post(client, envelope_body(), bearer="wrong")

    (row,) = rows(client)
    assert row.failure_reason == "bad_bearer"
    assert row.outcome == "rejected"


def test_malformed_envelope_is_recorded(client):
    post(client, b"{not json")

    (row,) = rows(client)
    assert row.failure_reason == "bad_payload"
    assert row.status_code == 400
    assert row.outcome == "rejected"


def test_duplicate_delivery_is_recorded_as_a_noop(client):
    body = envelope_body()
    post(client, body)
    post(client, body)

    noop = rows(client)[0]  # newest first
    assert noop.outcome == "noop"
    assert noop.status_code == 200
    assert noop.linear_action == "none"


def test_transient_failure_is_recorded_as_retrying(client):
    client.deps.client.fail_next["create_issue"] = LinearTransientError("429")
    response = post(client, envelope_body())
    assert response.status_code == 503

    (row,) = rows(client)
    assert row.outcome == "retrying"
    assert row.failure_reason == "transient"
    assert row.status_code == 503
    assert any(s.get("kind") == "linear_error" for s in row.trace)


def test_unknown_team_is_recorded(client):
    post(client, envelope_body(), team="nope")

    (row,) = rows(client)
    assert row.team == "nope"
    assert row.failure_reason == "unknown_team"
    assert row.status_code == 404


def test_a_delivery_log_write_failure_does_not_break_the_response(client, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("log table gone")

    monkeypatch.setattr("endor_linear_bridge.store.record_delivery", explode)

    response = post(client, envelope_body())

    assert response.status_code == 200
