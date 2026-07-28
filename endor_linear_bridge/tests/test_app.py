import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from endor_linear_bridge import metrics, store
from endor_linear_bridge.app import create_app
from endor_linear_bridge.auth import compute_signature
from endor_linear_bridge.handlers import HandlerDeps
from endor_linear_bridge.linear_client import LinearClient, LinearTransientError
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_handlers_open import (
    CONFIG,
    RUNTIME,
    envelope_body,
)

HMAC_SECRET = "secret"
BEARER = "token"
LINEAR_API_URL = "https://api.linear.app/graphql"


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


@pytest.fixture
def real_client_app(session_factory):
    """An app wired to a real LinearClient rather than FakeLinearClient.

    LINEAR_API_LATENCY is timed inside LinearClient.execute() (Fix 3a), so
    exercising it end to end needs the real client -- FakeLinearClient never
    calls execute() at all, and asserting against it would pass vacuously
    regardless of whether the metric is wired up correctly.
    """
    real_client = LinearClient(api_key="lin_key", api_url=LINEAR_API_URL)
    deps = HandlerDeps(
        session_factory=session_factory,
        client=real_client,
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )
    with TestClient(create_app(CONFIG, deps=deps)) as test_client:
        test_client.deps = deps
        yield test_client


def _linear_success_side_effect(request):
    """A minimal, generic 'everything succeeds' Linear GraphQL responder.

    Handling a real OPEN touches searchIssues (parent adoption check),
    issueCreate (parent, then sub-issue), so a fixed single response is not
    enough -- this dispatches on the operation name in the query text.
    """
    import json as _json

    body = _json.loads(request.content)
    query = body["query"]
    if "searchIssues" in query:
        data = {"searchIssues": {"nodes": []}}
    elif "issueCreate" in query:
        data = {
            "issueCreate": {
                "success": True,
                "issue": {"id": "i-mock", "identifier": "PLAT-1"},
            }
        }
    elif "issueUpdate" in query:
        data = {
            "issueUpdate": {
                "success": True,
                "issue": {"id": "i-mock", "identifier": "PLAT-1"},
            }
        }
    elif "commentCreate" in query:
        data = {"commentCreate": {"success": True}}
    else:  # pragma: no cover -- defensive; fail loudly on an unhandled op
        raise AssertionError(f"unexpected GraphQL query in test double: {query}")
    return httpx.Response(200, json={"data": data})


def _mock_linear_success(mock):
    return mock.post(LINEAR_API_URL).mock(side_effect=_linear_success_side_effect)


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


def _histogram_sample_count(histogram) -> float:
    for family in histogram.collect():
        for sample in family.samples:
            if sample.name.endswith("_count"):
                return sample.value
    return 0.0


def _counter_value(counter, *label_values) -> float:
    return counter.labels(*label_values)._value.get()


def test_unknown_team_metric_label_is_bounded(client):
    """Fix 2: the unknown-team branch runs before authentication, so the path
    segment is attacker-controlled. It must never become a Prometheus label
    value -- prometheus_client keeps one child metric per label tuple forever,
    so an unauthenticated caller could otherwise grow process memory and the
    /metrics payload without bound."""
    for bogus in ("aaaa-team", "bbbb-team", "cccc-team"):
        post(client, envelope_body(), team=bogus)

    text = client.get("/metrics").text

    assert 'team="unknown"' in text
    assert "aaaa-team" not in text
    assert "bbbb-team" not in text
    assert "cccc-team" not in text


def test_linear_api_latency_observes_a_sample_for_a_linear_call(real_client_app):
    """Fix 3a: the histogram times LinearClient.execute(), so a request that
    reaches Linear must record a sample. Needs the real LinearClient --
    FakeLinearClient never calls execute()."""
    with respx.mock() as mock:
        _mock_linear_success(mock)
        before = _histogram_sample_count(metrics.LINEAR_API_LATENCY)

        response = post(real_client_app, envelope_body())

        after = _histogram_sample_count(metrics.LINEAR_API_LATENCY)

    assert response.status_code == 200
    assert after > before


def test_linear_api_latency_is_not_observed_for_a_request_rejected_at_auth(
    real_client_app,
):
    """Fix 3a: a request rejected before handle_event runs makes no Linear
    call, so it must not move the metric -- it used to, back when the timer
    wrapped the whole handler in app.py."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post(LINEAR_API_URL)  # not expected to be called
        before = _histogram_sample_count(metrics.LINEAR_API_LATENCY)

        response = post(real_client_app, envelope_body(), bearer="wrong")

        after = _histogram_sample_count(metrics.LINEAR_API_LATENCY)

    assert response.status_code == 401
    assert after == before


def test_events_received_increments_for_a_request_that_later_fails(client):
    """Fix 3b: events_received_total must count arrivals, not successes, so a
    team whose every delivery fails to reach Linear does not report
    received=0 forever."""
    client.deps.client.fail_next["create_issue"] = LinearTransientError("429")
    before = _counter_value(metrics.EVENTS_RECEIVED, "plat", "open")

    response = post(client, envelope_body())

    after = _counter_value(metrics.EVENTS_RECEIVED, "plat", "open")
    assert response.status_code == 503
    assert after == before + 1


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
    client.deps.client.fail_next["create_issue"] = LinearTransientError("429")

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


def test_client_disconnect_during_body_read_returns_503(client, monkeypatch):
    """A body-read failure (e.g. a mid-upload disconnect) must be a 503, not
    the bare 500 Starlette's ServerErrorMiddleware would otherwise produce."""

    async def boom(self):
        raise RuntimeError("client disconnected")

    monkeypatch.setattr("starlette.requests.Request.body", boom)

    response = post(client, envelope_body())

    assert response.status_code == 503


def test_bad_bearer_rejection_log_carries_team_key(client, caplog):
    with caplog.at_level(logging.WARNING, logger="endor_linear_bridge.app"):
        post(client, envelope_body(), bearer="wrong")

    records = [r for r in caplog.records if "bearer" in r.message.lower()]
    assert records
    assert records[0].team_key == "plat"


def test_transient_failure_log_carries_notification_uuid(client, caplog):
    client.deps.client.fail_next["create_issue"] = LinearTransientError("429")

    with caplog.at_level(logging.WARNING, logger="endor_linear_bridge.app"):
        post(client, envelope_body())

    records = [r for r in caplog.records if "transient failure" in r.message.lower()]
    assert records
    assert records[0].notification_uuid == "notif-1"
    assert records[0].team_key == "plat"
    assert records[0].event == "open"
