import json

import pytest

from endor_linear_bridge import store
from endor_linear_bridge.envelope import parse_envelope
from endor_linear_bridge.handlers import TransientFailure, handle_event
from endor_linear_bridge.linear_client import LinearTransientError
from endor_linear_bridge.models import STATUS_OPEN, STATUS_RESOLVED
from endor_linear_bridge.tests.test_handlers_open import (  # noqa: F401
    deps,
    envelope_body,
)


async def send(deps, body):
    await handle_event(deps, "plat", parse_envelope(body), body)


def resolve_body(uuid="notif-1", project_uuid="proj-1", context_id="main"):
    """The resolve template omits the findings array entirely."""
    return json.dumps(
        {
            "event": "resolve",
            "notification": {
                "uuid": uuid,
                "project_uuid": project_uuid,
                "project_name": "webapp",
                "context_id": context_id,
            },
            "diff": {"new_finding_uuids": [], "resolved_finding_uuids": ["f1"]},
        }
    ).encode()


async def test_resolve_closes_the_sub_issue_with_a_comment(deps):
    await send(deps, envelope_body(event="open"))

    await send(deps, resolve_body())

    closes = [
        call for call in deps.client.calls_named("update_issue")
        if call["state_id"] == "s-done"
    ]
    assert any(call["issue_id"] == "i2" for call in closes)
    comments = deps.client.calls_named("create_comment")
    assert any("resolved" in c["body"].lower() for c in comments)


async def test_resolve_marks_the_row_resolved(deps):
    await send(deps, envelope_body(event="open"))

    await send(deps, resolve_body())

    with deps.session_factory() as session:
        assert store.get_notification(session, "notif-1").status == STATUS_RESOLVED


async def test_resolve_of_the_last_child_closes_the_parent(deps):
    await send(deps, envelope_body(event="open"))

    await send(deps, resolve_body())

    closes = [
        call for call in deps.client.calls_named("update_issue")
        if call["state_id"] == "s-done"
    ]
    assert {call["issue_id"] for call in closes} == {"i1", "i2"}
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_RESOLVED


async def test_resolve_with_open_siblings_leaves_the_parent_open(deps):
    await send(deps, envelope_body(event="open", uuid="notif-1", target="npm://lodash"))
    await send(deps, envelope_body(event="open", uuid="notif-2", target="npm://axios"))

    await send(deps, resolve_body(uuid="notif-1"))

    closes = [
        call for call in deps.client.calls_named("update_issue")
        if call["state_id"] == "s-done"
    ]
    assert {call["issue_id"] for call in closes} == {"i2"}
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_OPEN


async def test_resolving_both_children_closes_the_parent(deps):
    await send(deps, envelope_body(event="open", uuid="notif-1", target="npm://lodash"))
    await send(deps, envelope_body(event="open", uuid="notif-2", target="npm://axios"))

    await send(deps, resolve_body(uuid="notif-1"))
    await send(deps, resolve_body(uuid="notif-2"))

    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_RESOLVED


async def test_resolve_for_unknown_uuid_is_a_no_op_not_an_error(deps):
    """A stale notification must not mark the whole target misconfigured."""
    await send(deps, resolve_body(uuid="never-seen"))

    assert deps.client.calls_named("update_issue") == []


async def test_resolve_for_unknown_uuid_records_the_ledger(deps):
    body = resolve_body(uuid="never-seen")

    await send(deps, body)

    with deps.session_factory() as session:
        assert store.ledger_has(
            session, "never-seen", "resolve", store.payload_hash(body)
        )


async def test_resolve_of_an_already_resolved_row_is_a_no_op(deps):
    await send(deps, envelope_body(event="open"))
    await send(deps, resolve_body())
    before = len(deps.client.calls)

    await send(deps, resolve_body(uuid="notif-1"))

    assert len(deps.client.calls) == before


async def test_duplicate_resolve_delivery_is_a_no_op(deps):
    await send(deps, envelope_body(event="open"))
    body = resolve_body()

    await send(deps, body)
    before = len(deps.client.calls)
    await send(deps, body)

    assert len(deps.client.calls) == before


async def test_resolve_records_the_ledger(deps):
    await send(deps, envelope_body(event="open"))
    body = resolve_body()

    await send(deps, body)

    with deps.session_factory() as session:
        assert store.ledger_has(
            session, "notif-1", "resolve", store.payload_hash(body)
        )


async def test_resolve_keeps_the_finding_rows(deps):
    await send(deps, envelope_body(event="open"))

    await send(deps, resolve_body())

    with deps.session_factory() as session:
        assert store.all_findings(session, "notif-1")


async def test_linear_failure_during_resolve_is_transient_and_unledgered(deps):
    """Fix 5: RESOLVE acts on an issue id that may be months old and could
    just as easily hit a real Linear failure as OPEN's create_issue does."""
    await send(deps, envelope_body(event="open"))
    body = resolve_body()
    deps.client.fail_next["update_issue"] = LinearTransientError("linear degraded")

    with pytest.raises(TransientFailure):
        await send(deps, body)

    with deps.session_factory() as session:
        assert not store.ledger_has(
            session, "notif-1", "resolve", store.payload_hash(body)
        )


async def test_regression_after_resolve_creates_a_new_sub_issue(deps):
    """A4: a new notification uuid gets a fresh sub-issue under the same parent."""
    await send(deps, envelope_body(event="open", uuid="notif-1"))
    await send(deps, resolve_body(uuid="notif-1"))

    await send(deps, envelope_body(event="open", uuid="notif-2"))

    sub_issues = [
        call for call in deps.client.calls_named("create_issue")
        if call["parent_id"] is not None
    ]
    assert len(sub_issues) == 2
    with deps.session_factory() as session:
        first = store.get_notification(session, "notif-1")
        second = store.get_notification(session, "notif-2")
        assert first.linear_issue_id != second.linear_issue_id
        assert first.status == STATUS_RESOLVED
        assert second.status == STATUS_OPEN
        assert first.parent_id == second.parent_id
