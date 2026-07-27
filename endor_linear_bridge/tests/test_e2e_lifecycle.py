"""End-to-end: a realistic scan sequence through the real app.

Simulates what an operator sees across three endorctl scans:
  scan 1 -- lodash and axios both have findings  -> 1 parent, 2 sub-issues
  scan 2 -- a new critical finding on lodash     -> update on the lodash sub-issue
  scan 3 -- lodash fixed, then axios fixed       -> both close, parent closes last
"""

import json

import pytest
from fastapi.testclient import TestClient

from endor_linear_bridge import store
from endor_linear_bridge.app import create_app
from endor_linear_bridge.auth import compute_signature
from endor_linear_bridge.handlers import HandlerDeps
from endor_linear_bridge.models import STATUS_OPEN, STATUS_RESOLVED
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_handlers_open import CONFIG, RUNTIME

HMAC_SECRET = "secret"
BEARER = "token"


@pytest.fixture
def bridge(session_factory):
    deps = HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )
    with TestClient(create_app(CONFIG, deps=deps)) as client:
        client.deps = deps
        yield client


def deliver(bridge, payload):
    body = json.dumps(payload).encode()
    response = bridge.post(
        "/hooks/plat",
        content=body,
        headers={
            "Authorization": f"Bearer {BEARER}",
            "X-Endor-HMAC-Signature": compute_signature(body, HMAC_SECRET),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    return response


def notification(uuid, target, context_id="main"):
    return {
        "uuid": uuid,
        "project_uuid": "proj-1",
        "project_name": "webapp",
        "project_app_url": "https://app.endorlabs.com/t/ns/projects/proj-1",
        "ref_name": "main",
        "context_id": context_id,
        "policy_uuid": "pol-1",
        "policy_name": "Critical vulns",
        "policy_app_url": "https://app.endorlabs.com/t/ns/policies/pol-1",
        "aggregation": {
            "type": "AGGREGATION_TYPE_DEPENDENCY_ACROSS_PKG_VERSIONS",
            "target_name": target,
            "pkg_version_uuid": "",
        },
    }


def finding(fid, severity):
    return {
        "uuid": fid,
        "description": f"Vulnerability {fid}",
        "severity": severity,
        "dependency": "lodash@4.17.4",
        "package": "webapp@1.5.0",
        "finding_url": f"https://app.endorlabs.com/t/ns/findings/{fid}",
    }


def test_full_lifecycle_across_three_scans(bridge):
    fake = bridge.deps.client

    # --- Scan 1: lodash and axios both have findings -------------------------
    deliver(
        bridge,
        {
            "event": "open",
            "notification": notification("notif-lodash", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f1"], "resolved_finding_uuids": []},
            "findings": [finding("f1", "FINDING_LEVEL_HIGH")],
        },
    )
    deliver(
        bridge,
        {
            "event": "open",
            "notification": notification("notif-axios", "npm://axios"),
            "diff": {"new_finding_uuids": ["f2"], "resolved_finding_uuids": []},
            "findings": [finding("f2", "FINDING_LEVEL_MEDIUM")],
        },
    )

    creates = fake.calls_named("create_issue")
    assert len(creates) == 3, "one parent plus two sub-issues"
    assert creates[0]["parent_id"] is None
    assert creates[1]["parent_id"] == "i1"
    assert creates[2]["parent_id"] == "i1"
    assert creates[1]["priority"] == 2  # high
    assert creates[2]["priority"] == 3  # medium

    # --- Scan 2: a new critical finding lands on lodash ----------------------
    deliver(
        bridge,
        {
            "event": "update",
            "notification": notification("notif-lodash", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f3"], "resolved_finding_uuids": []},
            # Only the NEW finding -- Endor filters the payload.
            "findings": [finding("f3", "FINDING_LEVEL_CRITICAL")],
        },
    )

    last_update = fake.calls_named("update_issue")[-1]
    assert last_update["issue_id"] == "i2"
    assert last_update["priority"] == 1, "priority rises to urgent"
    assert last_update["label_ids"] == ("l-endorlabs", "l-crit")
    # The union survives: the original high finding is still described.
    assert "Vulnerability f1" in last_update["description"]
    assert "Vulnerability f3" in last_update["description"]
    # The comment mentions only the new one.
    assert "Vulnerability f3" in fake.calls_named("create_comment")[-1]["body"]
    assert "Vulnerability f1" not in fake.calls_named("create_comment")[-1]["body"]

    # --- Scan 3a: lodash fixed ----------------------------------------------
    deliver(
        bridge,
        {
            "event": "resolve",
            "notification": notification("notif-lodash", "npm://lodash"),
            "diff": {"new_finding_uuids": [], "resolved_finding_uuids": ["f1", "f3"]},
        },
    )

    closed = [c for c in fake.calls_named("update_issue") if c["state_id"] == "s-done"]
    assert {c["issue_id"] for c in closed} == {"i2"}, "parent stays open"
    with bridge.deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_OPEN

    # --- Scan 3b: axios fixed -> parent closes ------------------------------
    deliver(
        bridge,
        {
            "event": "resolve",
            "notification": notification("notif-axios", "npm://axios"),
            "diff": {"new_finding_uuids": [], "resolved_finding_uuids": ["f2"]},
        },
    )

    closed = [c for c in fake.calls_named("update_issue") if c["state_id"] == "s-done"]
    assert {c["issue_id"] for c in closed} == {"i1", "i2", "i3"}
    with bridge.deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_RESOLVED
        assert store.get_notification(session, "notif-lodash").status == STATUS_RESOLVED
        assert store.get_notification(session, "notif-axios").status == STATUS_RESOLVED


def test_every_event_redelivered_is_idempotent(bridge):
    """Endor retries on any non-200; replaying the whole sequence must be a no-op."""
    events = [
        {
            "event": "open",
            "notification": notification("notif-1", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f1"], "resolved_finding_uuids": []},
            "findings": [finding("f1", "FINDING_LEVEL_HIGH")],
        },
        {
            "event": "update",
            "notification": notification("notif-1", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f2"], "resolved_finding_uuids": []},
            "findings": [finding("f2", "FINDING_LEVEL_CRITICAL")],
        },
        {
            "event": "resolve",
            "notification": notification("notif-1", "npm://lodash"),
            "diff": {"new_finding_uuids": [], "resolved_finding_uuids": ["f1", "f2"]},
        },
    ]

    for payload in events:
        deliver(bridge, payload)
    call_count_after_first_pass = len(bridge.deps.client.calls)

    for payload in events:
        deliver(bridge, payload)

    assert len(bridge.deps.client.calls) == call_count_after_first_pass


def test_regression_after_full_resolution_opens_a_new_sub_issue(bridge):
    """A4, end to end: a regressed dependency gets a fresh sub-issue."""
    deliver(
        bridge,
        {
            "event": "open",
            "notification": notification("notif-1", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f1"], "resolved_finding_uuids": []},
            "findings": [finding("f1", "FINDING_LEVEL_HIGH")],
        },
    )
    deliver(
        bridge,
        {
            "event": "resolve",
            "notification": notification("notif-1", "npm://lodash"),
            "diff": {"new_finding_uuids": [], "resolved_finding_uuids": ["f1"]},
        },
    )

    # Months later the same dependency regresses -- new notification uuid.
    deliver(
        bridge,
        {
            "event": "open",
            "notification": notification("notif-2", "npm://lodash"),
            "diff": {"new_finding_uuids": ["f9"], "resolved_finding_uuids": []},
            "findings": [finding("f9", "FINDING_LEVEL_CRITICAL")],
        },
    )

    fake = bridge.deps.client
    sub_issues = [c for c in fake.calls_named("create_issue") if c["parent_id"]]
    assert len(sub_issues) == 2
    # The parent was reopened rather than duplicated.
    parents = [c for c in fake.calls_named("create_issue") if not c["parent_id"]]
    assert len(parents) == 1
    reopens = [
        c for c in fake.calls_named("update_issue")
        if c["issue_id"] == "i1" and c["state_id"] == "s-todo"
    ]
    assert len(reopens) == 1
