"""Aggregate queries that feed the dashboard's Overview and Teams screens."""

from dataclasses import dataclass
from datetime import timedelta

from endor_linear_bridge import store
from endor_linear_bridge.models import utcnow


@dataclass
class FakeFinding:
    uuid: str
    severity: str
    description: str = "d"
    dependency: str | None = None
    package: str | None = None
    finding_url: str | None = None


def _notification(session, uuid, *, team="plat", severities=("FINDING_LEVEL_HIGH",)):
    parent, _ = store.get_or_create_pending_parent(
        session, project_uuid="proj-1", context_id="main", team_key=team
    )
    row = store.create_pending_notification(
        session,
        notification_uuid=uuid,
        team_key=team,
        parent_id=parent.id,
        aggregation_target="npm://lodash",
    )
    store.replace_findings(
        session,
        uuid,
        [FakeFinding(uuid=f"{uuid}-f{i}", severity=s) for i, s in enumerate(severities)],
    )
    return row


def test_severity_totals_counts_findings_by_severity(session):
    _notification(session, "n1", severities=("FINDING_LEVEL_HIGH", "FINDING_LEVEL_LOW"))
    _notification(session, "n2", severities=("FINDING_LEVEL_HIGH",))
    session.commit()

    assert store.severity_totals(session) == {
        "FINDING_LEVEL_HIGH": 2,
        "FINDING_LEVEL_LOW": 1,
    }


def test_findings_total_counts_the_stored_union(session):
    _notification(session, "n1", severities=("FINDING_LEVEL_HIGH", "FINDING_LEVEL_LOW"))
    session.commit()

    assert store.findings_total(session) == 2


def test_issue_counts_by_team_and_status(session):
    open_row = _notification(session, "n1", team="plat")
    store.attach_linear_issue(session, open_row, "i1", "PLAT-1")
    closed_row = _notification(session, "n2", team="plat")
    store.attach_linear_issue(session, closed_row, "i2", "PLAT-2")
    store.mark_resolved(session, closed_row)
    _notification(session, "n3", team="sec")  # still pending: neither open nor closed
    session.commit()

    counts = store.issue_counts(session)
    assert counts["plat"] == {"open": 1, "closed": 1}
    assert counts["sec"] == {"open": 0, "closed": 0}


def test_severity_mix_groups_by_notification(session):
    _notification(session, "n1", severities=("FINDING_LEVEL_HIGH", "FINDING_LEVEL_HIGH"))
    _notification(session, "n2", severities=("FINDING_LEVEL_LOW",))
    session.commit()

    mix = store.severity_mix(session, ["n1", "n2", "n3"])
    assert mix["n1"] == {"FINDING_LEVEL_HIGH": 2}
    assert mix["n2"] == {"FINDING_LEVEL_LOW": 1}
    assert "n3" not in mix


def test_event_times_returns_parsed_events_in_the_window(session):
    old = store.record_delivery(
        session, team="plat", event_type="open", outcome="ok", status_code=200
    )
    old.received_at = utcnow() - timedelta(days=2)
    store.record_delivery(
        session, team="plat", event_type="update", outcome="ok", status_code=200
    )
    store.record_delivery(  # rejected before parse: no event type, excluded
        session, team="plat", event_type=None, outcome="rejected", status_code=401
    )
    session.commit()

    got = store.event_times(session, since=utcnow() - timedelta(hours=24))
    assert [event for _, event in got] == ["update"]
