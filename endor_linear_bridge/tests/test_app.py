import pytest
from fastapi.testclient import TestClient

from endor_linear_bridge import store
from endor_linear_bridge.app import create_app
from endor_linear_bridge.auth import compute_signature
from endor_linear_bridge.handlers import HandlerDeps
from endor_linear_bridge.linear_client import LinearTransientError
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_handlers_open import (
    CONFIG,
    RUNTIME,
    envelope_body,
)

HMAC_SECRET = "secret"
BEARER = "token"


@pytest.fixture
def app_deps(session_factory):
    return HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )


@pytest.fixture
def client(app_deps):
    with TestClient(create_app(CONFIG, deps=app_deps)) as test_client:
        test_client.deps = app_deps
        yield test_client


def post(client, body, *, team="plat", secret=HMAC_SECRET, bearer=BEARER, sign=True):
    headers = {"Content-Type": "application/json"}
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    if sign:
        headers["X-Endor-HMAC-Signature"] = compute_signature(body, secret)
    return client.post(f"/hooks/{team}", content=body, headers=headers)


def test_healthz_is_always_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200


def test_readyz_is_ok_when_runtimes_are_loaded(client):
    response = client.get("/readyz")

    assert response.status_code == 200


def test_metrics_endpoint_exposes_prometheus_text(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "events_received_total" in response.text


def test_valid_open_returns_200(client):
    response = post(client, envelope_body())

    assert response.status_code == 200


def test_valid_open_creates_issues(client):
    post(client, envelope_body())

    assert len(client.deps.client.calls_named("create_issue")) == 2


def test_unknown_team_returns_404(client):
    response = post(client, envelope_body(), team="nope")

    assert response.status_code == 404


def test_missing_bearer_returns_401(client):
    response = post(client, envelope_body(), bearer=None)

    assert response.status_code == 401


def test_wrong_bearer_returns_401(client):
    response = post(client, envelope_body(), bearer="wrong")

    assert response.status_code == 401


def test_missing_hmac_signature_returns_401(client):
    response = post(client, envelope_body(), sign=False)

    assert response.status_code == 401


def test_wrong_hmac_secret_returns_401(client):
    response = post(client, envelope_body(), secret="not-the-secret")

    assert response.status_code == 401


def test_tampered_body_returns_401(client):
    body = envelope_body()
    headers = {
        "Authorization": f"Bearer {BEARER}",
        "X-Endor-HMAC-Signature": compute_signature(body, HMAC_SECRET),
    }

    response = client.post(
        "/hooks/plat", content=envelope_body(uuid="tampered"), headers=headers
    )

    assert response.status_code == 401


def test_auth_failure_creates_no_issues(client):
    post(client, envelope_body(), bearer="wrong")

    assert client.deps.client.calls == []


def test_malformed_json_returns_400(client):
    response = post(client, b"{not json")

    assert response.status_code == 400


def test_missing_required_field_returns_400(client):
    response = post(client, b'{"event":"open","notification":{}}')

    assert response.status_code == 400


def test_unknown_event_returns_400(client):
    body = envelope_body().replace(b'"event": "open"', b'"event": "deleted"')

    response = post(client, body)

    assert response.status_code == 400


def test_transient_linear_failure_returns_503(client):
    client.deps.client.fail_next_create = LinearTransientError("429")

    response = post(client, envelope_body())

    assert response.status_code == 503


def test_unexpected_exception_returns_503_not_500(client, monkeypatch):
    """Endor retries 5xx but gives up on 4xx -- a crash must never surface as 500."""
    async def explode(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("endor_linear_bridge.app.handle_event", explode)

    response = post(client, envelope_body())

    assert response.status_code == 503


def test_readiness_is_503_before_startup_completes():
    """A not-ready service must fail readiness rather than accept traffic.

    Tested against readiness_status directly: entering a TestClient would run
    the lifespan, which tries to reach the real Linear API.
    """
    from endor_linear_bridge.app import AppState, readiness_status

    assert readiness_status(AppState(config=CONFIG, deps=None, ready=False)) == 503


def test_readiness_is_503_when_the_database_is_unreachable(app_deps):
    from endor_linear_bridge.app import AppState, readiness_status

    def broken_factory():
        raise RuntimeError("database gone")

    state = AppState(
        config=CONFIG,
        deps=HandlerDeps(
            session_factory=broken_factory,
            client=app_deps.client,
            runtimes=app_deps.runtimes,
            config=CONFIG,
        ),
        ready=True,
    )

    assert readiness_status(state) == 503


def test_hooks_rejects_get(client):
    response = client.get("/hooks/plat")

    assert response.status_code == 405


def test_successful_response_body_is_json(client):
    response = post(client, envelope_body())

    assert response.json() == {"status": "ok"}


def test_json_log_formatter_emits_one_json_object_per_record():
    import json
    import logging

    from endor_linear_bridge.app import JsonLogFormatter

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="created sub-issue", args=(), exc_info=None,
    )

    parsed = json.loads(JsonLogFormatter().format(record))

    assert parsed["message"] == "created sub-issue"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test"


def test_json_log_formatter_promotes_context_fields():
    import json
    import logging

    from endor_linear_bridge.app import JsonLogFormatter

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="processed", args=(), exc_info=None,
    )
    record.notification_uuid = "notif-1"
    record.team_key = "plat"
    record.event = "open"
    record.linear_identifier = "PLAT-12"

    parsed = json.loads(JsonLogFormatter().format(record))

    assert parsed["notification_uuid"] == "notif-1"
    assert parsed["team_key"] == "plat"
    assert parsed["event"] == "open"
    assert parsed["linear_identifier"] == "PLAT-12"


def test_json_log_formatter_omits_absent_context_fields():
    import json
    import logging

    from endor_linear_bridge.app import JsonLogFormatter

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="startup complete", args=(), exc_info=None,
    )

    parsed = json.loads(JsonLogFormatter().format(record))

    assert "notification_uuid" not in parsed
    assert "linear_identifier" not in parsed


def test_configure_logging_is_idempotent():
    import logging

    from endor_linear_bridge.app import configure_logging

    configure_logging()
    first = len(logging.getLogger().handlers)
    configure_logging()

    assert len(logging.getLogger().handlers) == first
