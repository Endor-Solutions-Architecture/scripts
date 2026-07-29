from dataclasses import dataclass

from endor_linear_bridge import store
from endor_linear_bridge.models import STATUS_OPEN, STATUS_PENDING, STATUS_RESOLVED


@dataclass
class F:
    uuid: str
    severity: str = "FINDING_LEVEL_HIGH"
    description: str = "a finding"
    dependency: str | None = "lodash@4.17.4"
    package: str | None = "webapp@1.5.0"
    finding_url: str | None = "https://example.test/f"


def make_parent(session, project_uuid="proj-1", context_id="main", team_key="plat"):
    parent, _ = store.get_or_create_pending_parent(
        session, project_uuid=project_uuid, context_id=context_id, team_key=team_key
    )
    return parent


def make_notification(session, uuid="notif-1", parent=None, team_key="plat"):
    parent = parent or make_parent(session)
    return store.create_pending_notification(
        session,
        notification_uuid=uuid,
        team_key=team_key,
        parent_id=parent.id,
        aggregation_target="npm://lodash",
    )


def test_payload_hash_is_stable_and_content_dependent():
    assert store.payload_hash(b"a") == store.payload_hash(b"a")
    assert store.payload_hash(b"a") != store.payload_hash(b"b")


def test_ledger_has_is_false_before_recording(session):
    assert store.ledger_has(session, "notif-1", "open", "hash-1") is False


def test_record_event_then_ledger_has_is_true(session):
    store.record_event(session, "notif-1", "open", "hash-1")
    session.commit()

    assert store.ledger_has(session, "notif-1", "open", "hash-1") is True


def test_ledger_distinguishes_event_and_hash(session):
    store.record_event(session, "notif-1", "open", "hash-1")
    session.commit()

    assert store.ledger_has(session, "notif-1", "update", "hash-1") is False
    assert store.ledger_has(session, "notif-1", "open", "hash-2") is False


def test_record_event_is_idempotent_for_the_same_key(session):
    store.record_event(session, "notif-1", "open", "hash-1")
    session.commit()
    store.record_event(session, "notif-1", "open", "hash-1")
    session.commit()

    assert store.ledger_has(session, "notif-1", "open", "hash-1") is True


def test_get_or_create_pending_parent_creates_once(session):
    first, created_first = store.get_or_create_pending_parent(
        session, project_uuid="proj-1", context_id="main", team_key="plat"
    )
    session.commit()
    second, created_second = store.get_or_create_pending_parent(
        session, project_uuid="proj-1", context_id="main", team_key="plat"
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert first.status == STATUS_PENDING


def test_parent_is_scoped_by_context_and_team(session):
    a = make_parent(session, context_id="main")
    session.commit()
    b = make_parent(session, context_id="release-2")
    session.commit()
    c = make_parent(session, context_id="main", team_key="sec")
    session.commit()

    assert len({a.id, b.id, c.id}) == 3


def test_create_pending_notification_starts_pending(session):
    row = make_notification(session)
    session.commit()

    assert row.status == STATUS_PENDING
    assert row.linear_issue_id is None
    assert row.aggregation_target == "npm://lodash"


def test_get_notification_returns_none_for_unknown(session):
    assert store.get_notification(session, "nope") is None


def test_get_notification_finds_a_created_row(session):
    make_notification(session, uuid="notif-7")
    session.commit()

    found = store.get_notification(session, "notif-7")

    assert found is not None
    assert found.notification_uuid == "notif-7"


def test_attach_linear_issue_sets_ids_and_opens(session):
    row = make_notification(session)

    store.attach_linear_issue(session, row, "lin-1", "PLAT-12")
    session.commit()

    assert row.linear_issue_id == "lin-1"
    assert row.linear_identifier == "PLAT-12"
    assert row.status == STATUS_OPEN


def test_attach_linear_issue_works_for_parents(session):
    parent = make_parent(session)

    store.attach_linear_issue(session, parent, "lin-p", "PLAT-1")
    session.commit()

    assert parent.status == STATUS_OPEN
    assert parent.linear_identifier == "PLAT-1"


def test_mark_resolved_and_mark_open(session):
    row = make_notification(session)
    store.attach_linear_issue(session, row, "lin-1", "PLAT-12")

    store.mark_resolved(session, row)
    session.commit()
    assert row.status == STATUS_RESOLVED

    store.mark_open(session, row)
    session.commit()
    assert row.status == STATUS_OPEN
    assert row.linear_issue_id == "lin-1"


def test_replace_findings_inserts_all(session):
    make_notification(session)
    session.commit()

    store.replace_findings(session, "notif-1", [F("f1"), F("f2")])
    session.commit()

    assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
        "f1",
        "f2",
    }


def test_replace_findings_drops_findings_absent_from_the_new_set(session):
    make_notification(session)
    store.replace_findings(session, "notif-1", [F("f1"), F("f2")])
    session.commit()

    store.replace_findings(session, "notif-1", [F("f2")])
    session.commit()

    assert [f.finding_uuid for f in store.all_findings(session, "notif-1")] == ["f2"]


def test_upsert_findings_adds_without_removing(session):
    make_notification(session)
    store.replace_findings(session, "notif-1", [F("f1")])
    session.commit()

    inserted = store.upsert_findings(session, "notif-1", [F("f2"), F("f3")])
    session.commit()

    assert inserted == 2
    assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
        "f1",
        "f2",
        "f3",
    }


def test_upsert_findings_preserves_first_seen_at_for_existing(session):
    make_notification(session)
    store.replace_findings(session, "notif-1", [F("f1")])
    session.commit()
    original = store.all_findings(session, "notif-1")[0].first_seen_at

    inserted = store.upsert_findings(
        session, "notif-1", [F("f1", description="changed")]
    )
    session.commit()

    rows = store.all_findings(session, "notif-1")
    assert inserted == 0
    assert len(rows) == 1
    assert rows[0].first_seen_at == original


def test_upsert_findings_updates_mutable_fields_of_existing(session):
    make_notification(session)
    store.replace_findings(session, "notif-1", [F("f1", severity="FINDING_LEVEL_LOW")])
    session.commit()

    store.upsert_findings(
        session, "notif-1", [F("f1", severity="FINDING_LEVEL_CRITICAL")]
    )
    session.commit()

    assert store.all_findings(session, "notif-1")[0].severity == (
        "FINDING_LEVEL_CRITICAL"
    )


def test_findings_are_scoped_per_notification(session):
    parent = make_parent(session)
    make_notification(session, uuid="notif-1", parent=parent)
    make_notification(session, uuid="notif-2", parent=parent)
    store.replace_findings(session, "notif-1", [F("f1")])
    store.replace_findings(session, "notif-2", [F("f2")])
    session.commit()

    assert [f.finding_uuid for f in store.all_findings(session, "notif-1")] == ["f1"]


def test_notification_finding_exposes_uuid_for_rendering(session):
    """render.FindingLike expects a .uuid attribute."""
    make_notification(session)
    store.replace_findings(session, "notif-1", [F("f1")])
    session.commit()

    assert store.all_findings(session, "notif-1")[0].uuid == "f1"


def test_count_unresolved_siblings_excludes_self(session):
    parent = make_parent(session)
    make_notification(session, uuid="notif-1", parent=parent)
    session.commit()

    assert store.count_unresolved_siblings(session, parent.id, "notif-1") == 0


def test_count_unresolved_siblings_counts_open_and_pending(session):
    parent = make_parent(session)
    make_notification(session, uuid="notif-1", parent=parent)
    open_row = make_notification(session, uuid="notif-2", parent=parent)
    store.attach_linear_issue(session, open_row, "lin-2", "PLAT-2")
    make_notification(session, uuid="notif-3", parent=parent)  # stays pending
    session.commit()

    assert store.count_unresolved_siblings(session, parent.id, "notif-1") == 2


def test_count_unresolved_siblings_ignores_resolved(session):
    parent = make_parent(session)
    make_notification(session, uuid="notif-1", parent=parent)
    other = make_notification(session, uuid="notif-2", parent=parent)
    store.attach_linear_issue(session, other, "lin-2", "PLAT-2")
    store.mark_resolved(session, other)
    session.commit()

    assert store.count_unresolved_siblings(session, parent.id, "notif-1") == 0
