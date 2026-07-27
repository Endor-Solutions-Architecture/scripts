import pytest

from endor_linear_bridge import store
from endor_linear_bridge.envelope import parse_envelope
from endor_linear_bridge.handlers import handle_event
from endor_linear_bridge.models import STATUS_OPEN
from endor_linear_bridge.tests.test_handlers_open import (  # noqa: F401
    deps,
    envelope_body,
)


async def send(deps, body):
    await handle_event(deps, "plat", parse_envelope(body), body)


async def open_first(deps, findings=(("f1", "FINDING_LEVEL_LOW"),)):
    await send(deps, envelope_body(event="open", findings=findings))


async def test_update_renders_the_union_not_just_new_findings(deps):
    """A1 regression test: previously reported findings must survive."""
    await open_first(deps, findings=(("f1", "FINDING_LEVEL_LOW"),))

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),)),
    )

    description = deps.client.calls_named("update_issue")[-1]["description"]
    assert "Finding f1" in description
    assert "Finding f2" in description


async def test_update_stores_the_union(deps):
    await open_first(deps)

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),)),
    )

    with deps.session_factory() as session:
        assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
            "f1",
            "f2",
        }


async def test_update_comments_with_only_the_new_findings(deps):
    await open_first(deps)

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),)),
    )

    body = deps.client.calls_named("create_comment")[-1]["body"]
    assert "1 new finding" in body
    assert "Finding f2" in body
    assert "Finding f1" not in body


async def test_update_recomputes_priority_when_severity_rises(deps):
    """A5: priority comes from the union's max severity."""
    await open_first(deps, findings=(("f1", "FINDING_LEVEL_LOW"),))

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_CRITICAL"),)),
    )

    assert deps.client.calls_named("update_issue")[-1]["priority"] == 1


async def test_update_sends_the_complete_label_set(deps):
    """labelIds is a full replacement -- a stale severity label must not survive."""
    await open_first(deps, findings=(("f1", "FINDING_LEVEL_LOW"),))

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_CRITICAL"),)),
    )

    labels = deps.client.calls_named("update_issue")[-1]["label_ids"]
    assert labels == ("l-endorlabs", "l-crit")
    assert "l-low" not in labels


async def test_update_keeps_priority_when_severity_does_not_rise(deps):
    await open_first(deps, findings=(("f1", "FINDING_LEVEL_CRITICAL"),))

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_LOW"),)),
    )

    assert deps.client.calls_named("update_issue")[-1]["priority"] == 1


async def test_update_targets_the_existing_sub_issue(deps):
    await open_first(deps)

    await send(
        deps,
        envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),)),
    )

    assert deps.client.calls_named("update_issue")[-1]["issue_id"] == "i2"


async def test_update_for_unknown_uuid_falls_back_to_create(deps):
    """Handles an update delivered before its open, or after a lost database."""
    await send(
        deps,
        envelope_body(event="update", findings=(("f1", "FINDING_LEVEL_HIGH"),)),
    )

    creates = deps.client.calls_named("create_issue")
    assert len(creates) == 2  # parent + sub-issue
    with deps.session_factory() as session:
        row = store.get_notification(session, "notif-1")
        assert row is not None
        assert row.status == STATUS_OPEN


async def test_duplicate_update_delivery_is_a_no_op(deps):
    await open_first(deps)
    body = envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),))

    await send(deps, body)
    before = len(deps.client.calls)
    await send(deps, body)

    assert len(deps.client.calls) == before


async def test_a_different_update_for_the_same_notification_is_processed(deps):
    """The ledger keys on the payload hash, so distinct updates both apply."""
    await open_first(deps)

    await send(
        deps, envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),))
    )
    await send(
        deps, envelope_body(event="update", findings=(("f3", "FINDING_LEVEL_HIGH"),))
    )

    with deps.session_factory() as session:
        assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
            "f1",
            "f2",
            "f3",
        }


async def test_update_records_the_ledger(deps):
    await open_first(deps)
    body = envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),))

    await send(deps, body)

    with deps.session_factory() as session:
        assert store.ledger_has(
            session, "notif-1", "update", store.payload_hash(body)
        )


async def test_update_reopens_a_resolved_sub_issue(deps):
    await open_first(deps)
    with deps.session_factory() as session:
        row = store.get_notification(session, "notif-1")
        store.mark_resolved(session, row)
        session.commit()

    await send(
        deps, envelope_body(event="update", findings=(("f2", "FINDING_LEVEL_HIGH"),))
    )

    updates = deps.client.calls_named("update_issue")
    assert any(call["state_id"] == "s-todo" for call in updates)
    with deps.session_factory() as session:
        assert store.get_notification(session, "notif-1").status == STATUS_OPEN
