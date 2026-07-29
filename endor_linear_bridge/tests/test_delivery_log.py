"""The delivery log: the append-only table behind the dashboard's Deliveries view.

One row per webhook the bridge accepted OR rejected, written after the handler
resolves. Rejected-before-parse rows have no notification UUID or target.
"""

from datetime import timedelta

from endor_linear_bridge import store
from endor_linear_bridge.models import utcnow


def _record(session, **overrides):
    defaults = dict(
        team="plat",
        event_type="open",
        notification_uuid="notif-1",
        target="npm://lodash",
        project="webapp",
        branch="main",
        findings_new=3,
        findings_total=3,
        linear_identifier="PLAT-142",
        linear_action="created",
        parent_identifier="PLAT-100",
        outcome="ok",
        status_code=200,
        failure_reason=None,
        latency_ms=412,
        trace=[{"step": "Signature verified", "detail": "hmac ok", "ok": True}],
    )
    defaults.update(overrides)
    return store.record_delivery(session, **defaults)


def test_record_and_read_back_a_delivery(session):
    row = _record(session)
    session.commit()

    deliveries = store.recent_deliveries(session, since=None)
    assert len(deliveries) == 1
    got = deliveries[0]
    assert got.id == row.id
    assert got.team == "plat"
    assert got.outcome == "ok"
    assert got.trace[0]["step"] == "Signature verified"


def test_rejected_delivery_needs_no_parsed_fields(session):
    _record(
        session,
        event_type=None,
        notification_uuid=None,
        target=None,
        project=None,
        branch=None,
        findings_new=None,
        findings_total=None,
        linear_identifier=None,
        linear_action="none",
        parent_identifier=None,
        outcome="rejected",
        status_code=401,
        failure_reason="bad_hmac",
        trace=[{"step": "Signature check", "detail": "mismatch", "ok": False}],
    )
    session.commit()

    got = store.recent_deliveries(session, since=None)[0]
    assert got.notification_uuid is None
    assert got.failure_reason == "bad_hmac"


def test_recent_deliveries_newest_first_with_limit(session):
    for i in range(3):
        _record(session, notification_uuid=f"notif-{i}")
    session.commit()

    got = store.recent_deliveries(session, since=None, limit=2)
    assert len(got) == 2
    assert got[0].id > got[1].id


def test_recent_deliveries_filters_by_event_and_failure(session):
    _record(session, event_type="open")
    _record(session, event_type="update", outcome="retrying", status_code=503,
            failure_reason="transient")
    session.commit()

    assert len(store.recent_deliveries(session, since=None, event_type="update")) == 1
    failed = store.recent_deliveries(session, since=None, failed_only=True)
    assert len(failed) == 1
    assert failed[0].outcome == "retrying"


def test_recent_deliveries_searches_uuid_target_and_linear_id(session):
    _record(session, notification_uuid="abc-123", target="npm://lodash",
            linear_identifier="PLAT-142")
    _record(session, notification_uuid="def-456", target="pypi://requests",
            linear_identifier="PLAT-143")
    session.commit()

    assert len(store.recent_deliveries(session, since=None, search="abc-123")) == 1
    assert len(store.recent_deliveries(session, since=None, search="requests")) == 1
    assert len(store.recent_deliveries(session, since=None, search="PLAT-142")) == 1
    assert len(store.recent_deliveries(session, since=None, search="nowhere")) == 0


def test_recent_deliveries_respects_the_time_window(session):
    old = _record(session, notification_uuid="old")
    old.received_at = utcnow() - timedelta(days=2)
    _record(session, notification_uuid="new")
    session.commit()

    got = store.recent_deliveries(session, since=utcnow() - timedelta(hours=24))
    assert [d.notification_uuid for d in got] == ["new"]


def test_delivery_summary_counts_by_outcome(session):
    _record(session)
    _record(session, outcome="noop")
    _record(session, outcome="retrying", status_code=503, failure_reason="transient")
    _record(session, outcome="rejected", status_code=401, failure_reason="bad_hmac")
    session.commit()

    summary = store.delivery_summary(session, since=None)
    assert summary == {
        "received": 4, "ok": 1, "noop": 1, "retrying": 1, "rejected": 1,
    }


def test_team_delivery_stats_aggregates_per_team(session):
    _record(session, team="plat", event_type="open")
    _record(session, team="plat", event_type="update")
    _record(session, team="sec", event_type="resolve",
            outcome="rejected", status_code=401, failure_reason="bad_hmac")
    session.commit()

    stats = store.team_delivery_stats(session, since=None)
    assert stats["plat"]["open"] == 1
    assert stats["plat"]["update"] == 1
    assert stats["plat"]["failed"] == 0
    assert stats["sec"]["failed"] == 1
    assert stats["sec"]["last_event_at"] is not None


def test_failure_counts_by_reason(session):
    _record(session, outcome="retrying", status_code=503, failure_reason="transient")
    _record(session, outcome="retrying", status_code=503, failure_reason="transient")
    _record(session, outcome="rejected", status_code=401, failure_reason="bad_hmac")
    _record(session)
    session.commit()

    assert store.failure_counts(session, since=None) == {
        "transient": 2, "bad_hmac": 1,
    }


def test_prune_delivery_log_removes_only_old_rows(session):
    old = _record(session, notification_uuid="old")
    old.received_at = utcnow() - timedelta(days=40)
    _record(session, notification_uuid="new")
    session.commit()

    removed = store.prune_delivery_log(session, older_than=utcnow() - timedelta(days=30))
    session.commit()

    assert removed == 1
    kept = store.recent_deliveries(session, since=None)
    assert [d.notification_uuid for d in kept] == ["new"]
