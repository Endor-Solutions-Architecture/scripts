import pytest

from endor_linear_bridge import store
from endor_linear_bridge.config import Config, TeamConfig
from endor_linear_bridge.envelope import parse_envelope
from endor_linear_bridge.handlers import HandlerDeps, TransientFailure, handle_event
from endor_linear_bridge.linear_cache import TeamRuntime
from endor_linear_bridge.linear_client import LinearRequestError, LinearTransientError
from endor_linear_bridge.models import STATUS_OPEN, STATUS_PENDING, STATUS_RESOLVED
from endor_linear_bridge.render import (
    NOTIFICATION_FOOTER_PREFIX,
    PARENT_PROJECT_FOOTER_PREFIX,
    PARENT_TEAM_FOOTER_PREFIX,
)
from endor_linear_bridge.tests.linear_fake import FakeLinearClient

import json

TEAM_CONFIG = TeamConfig(
    key="plat",
    linear_team_key="PLAT",
    hmac_secret="secret",
    open_state=None,
    close_state=None,
    reopen_state=None,
    labels=("endorlabs",),
    priority_from_severity=True,
    severity_labels=True,
    severity_label_prefix="endor-",
)

RUNTIME = TeamRuntime(
    config=TEAM_CONFIG,
    linear_team_id="t1",
    open_state_id="s-todo",
    close_state_id="s-done",
    reopen_state_id="s-todo",
    base_label_ids=("l-endorlabs",),
    severity_label_ids={
        "critical": "l-crit",
        "high": "l-high",
        "medium": "l-med",
        "low": "l-low",
    },
)

CONFIG = Config(
    linear_api_key="lin_key",
    linear_api_url="https://api.linear.app/graphql",
    inbound_bearer_token="token",
    database_url="sqlite:///:memory:",
    max_findings_per_issue=50,
    teams={"plat": TEAM_CONFIG},
)


def envelope_body(
    event="open",
    uuid="notif-1",
    project_uuid="proj-1",
    context_id="main",
    target="npm://lodash",
    findings=(("f1", "FINDING_LEVEL_CRITICAL"),),
    new_uuids=None,
):
    payload = {
        "event": event,
        "notification": {
            "uuid": uuid,
            "project_uuid": project_uuid,
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
        },
        "diff": {
            "new_finding_uuids": list(
                new_uuids if new_uuids is not None else [f[0] for f in findings]
            ),
            "resolved_finding_uuids": [],
        },
        "findings": [
            {
                "uuid": fid,
                "description": f"Finding {fid}",
                "severity": severity,
                "dependency": "lodash@4.17.4",
                "package": "webapp@1.5.0",
                "finding_url": f"https://app.endorlabs.com/t/ns/findings/{fid}",
            }
            for fid, severity in findings
        ],
    }
    return json.dumps(payload).encode()


@pytest.fixture
def deps(session_factory):
    return HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )


async def send(deps, body):
    await handle_event(deps, "plat", parse_envelope(body), body)


async def test_open_creates_parent_then_sub_issue(deps):
    await send(deps, envelope_body())

    creates = deps.client.calls_named("create_issue")
    assert len(creates) == 2
    assert creates[0]["parent_id"] is None
    assert creates[0]["title"] == "[Endor Labs] webapp — main"
    assert creates[1]["parent_id"] == "i1"
    assert creates[1]["title"] == "[Dep] npm://lodash"


async def test_open_persists_rows_as_open(deps):
    await send(deps, envelope_body())

    with deps.session_factory() as session:
        row = store.get_notification(session, "notif-1")
        assert row.status == STATUS_OPEN
        assert row.linear_issue_id == "i2"
        assert row.linear_identifier == "PLAT-2"
        parent, created = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert created is False
        assert parent.status == STATUS_OPEN


async def test_open_stores_the_full_finding_set(deps):
    body = envelope_body(
        findings=(("f1", "FINDING_LEVEL_LOW"), ("f2", "FINDING_LEVEL_HIGH"))
    )

    await send(deps, body)

    with deps.session_factory() as session:
        assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
            "f1",
            "f2",
        }


async def test_open_sets_priority_and_labels_from_max_severity(deps):
    body = envelope_body(
        findings=(("f1", "FINDING_LEVEL_LOW"), ("f2", "FINDING_LEVEL_CRITICAL"))
    )

    await send(deps, body)

    sub_issue = deps.client.calls_named("create_issue")[1]
    assert sub_issue["priority"] == 1
    assert sub_issue["label_ids"] == ("l-endorlabs", "l-crit")
    assert sub_issue["state_id"] == "s-todo"


async def test_open_embeds_the_recovery_footer(deps):
    await send(deps, envelope_body())

    sub_issue = deps.client.calls_named("create_issue")[1]
    assert f"{NOTIFICATION_FOOTER_PREFIX} notif-1" in sub_issue["description"]


async def test_open_parent_description_has_the_project_footer(deps):
    await send(deps, envelope_body())

    parent = deps.client.calls_named("create_issue")[0]
    assert f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1" in parent["description"]


async def test_open_records_the_ledger(deps):
    body = envelope_body()

    await send(deps, body)

    with deps.session_factory() as session:
        assert store.ledger_has(
            session, "notif-1", "open", store.payload_hash(body)
        )


async def test_duplicate_open_delivery_is_a_no_op(deps):
    body = envelope_body()

    await send(deps, body)
    await send(deps, body)

    assert len(deps.client.calls_named("create_issue")) == 2


async def test_second_dependency_reuses_the_existing_parent(deps):
    await send(deps, envelope_body(uuid="notif-1", target="npm://lodash"))
    await send(deps, envelope_body(uuid="notif-2", target="npm://axios"))

    creates = deps.client.calls_named("create_issue")
    assert len(creates) == 3
    assert creates[2]["parent_id"] == "i1"
    assert creates[2]["title"] == "[Dep] npm://axios"


async def test_different_context_gets_its_own_parent(deps):
    await send(deps, envelope_body(uuid="notif-1", context_id="main"))
    await send(deps, envelope_body(uuid="notif-2", context_id="release-2"))

    parents = [
        call for call in deps.client.calls_named("create_issue")
        if call["parent_id"] is None
    ]
    assert len(parents) == 2


async def test_open_reopens_a_resolved_parent(deps):
    await send(deps, envelope_body(uuid="notif-1"))
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        store.mark_resolved(session, parent)
        session.commit()

    await send(deps, envelope_body(uuid="notif-2", target="npm://axios"))

    updates = deps.client.calls_named("update_issue")
    assert any(
        call["issue_id"] == "i1" and call["state_id"] == "s-todo" for call in updates
    )
    comments = deps.client.calls_named("create_comment")
    assert any("new findings" in c["body"].lower() for c in comments)
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_OPEN


async def test_open_for_a_known_uuid_updates_instead_of_duplicating(deps):
    """A resent OPEN with different content must not create a second issue."""
    await send(deps, envelope_body(findings=(("f1", "FINDING_LEVEL_LOW"),)))

    await send(
        deps,
        envelope_body(
            findings=(("f1", "FINDING_LEVEL_LOW"), ("f2", "FINDING_LEVEL_CRITICAL"))
        ),
    )

    assert len(deps.client.calls_named("create_issue")) == 2
    assert deps.client.calls_named("update_issue")
    with deps.session_factory() as session:
        assert {f.finding_uuid for f in store.all_findings(session, "notif-1")} == {
            "f1",
            "f2",
        }


async def test_open_replaces_findings_rather_than_merging(deps):
    """The OPEN payload is authoritative and complete, so absent findings drop."""
    await send(
        deps,
        envelope_body(
            findings=(("f1", "FINDING_LEVEL_LOW"), ("f2", "FINDING_LEVEL_LOW"))
        ),
    )

    await send(deps, envelope_body(findings=(("f2", "FINDING_LEVEL_LOW"),)))

    with deps.session_factory() as session:
        assert [f.finding_uuid for f in store.all_findings(session, "notif-1")] == [
            "f2"
        ]


async def test_transient_linear_failure_leaves_a_pending_row(deps):
    deps.client.fail_next["create_issue"] = LinearTransientError("429 forever")

    with pytest.raises(TransientFailure):
        await send(deps, envelope_body())

    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.status == STATUS_PENDING


async def test_retry_after_crash_adopts_the_existing_sub_issue(deps):
    """A2: the crash window between issueCreate and the DB write must not duplicate."""
    body = envelope_body()

    # First delivery: parent succeeds, sub-issue creation "succeeds" in Linear but
    # the process dies before the ids are written. Simulate by seeding the issue
    # Linear already holds and leaving the row pending.
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        store.attach_linear_issue(session, parent, "i-parent", "PLAT-1")
        store.create_pending_notification(
            session,
            notification_uuid="notif-1",
            team_key="plat",
            parent_id=parent.id,
            aggregation_target="npm://lodash",
        )
        session.commit()
    orphan = deps.client.seed_issue(
        description=f"body\n{NOTIFICATION_FOOTER_PREFIX} notif-1",
        identifier="PLAT-42",
    )

    await send(deps, body)

    assert deps.client.calls_named("create_issue") == []
    assert deps.client.calls_named("search_issues")
    with deps.session_factory() as session:
        row = store.get_notification(session, "notif-1")
        assert row.linear_issue_id == orphan["id"]
        assert row.linear_identifier == "PLAT-42"
        assert row.status == STATUS_OPEN


async def test_retry_after_crash_creates_when_no_orphan_is_found(deps):
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        store.attach_linear_issue(session, parent, "i-parent", "PLAT-1")
        store.create_pending_notification(
            session,
            notification_uuid="notif-1",
            team_key="plat",
            parent_id=parent.id,
            aggregation_target="npm://lodash",
        )
        session.commit()

    await send(deps, envelope_body())

    assert len(deps.client.calls_named("create_issue")) == 1
    with deps.session_factory() as session:
        assert store.get_notification(session, "notif-1").status == STATUS_OPEN


async def test_pending_parent_is_adopted_from_search(deps):
    with deps.session_factory() as session:
        store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        session.commit()
    deps.client.seed_issue(
        description=(
            f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1\nEndor-context-id: main\n"
            f"{PARENT_TEAM_FOOTER_PREFIX} plat"
        ),
        identifier="PLAT-7",
    )

    await send(deps, envelope_body())

    creates = deps.client.calls_named("create_issue")
    assert len(creates) == 1  # only the sub-issue
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.linear_identifier == "PLAT-7"


async def test_pending_parent_ignores_a_different_context(deps):
    with deps.session_factory() as session:
        store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        session.commit()
    deps.client.seed_issue(
        description=(
            f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1\nEndor-context-id: release-2\n"
            f"{PARENT_TEAM_FOOTER_PREFIX} plat"
        ),
        identifier="PLAT-7",
    )

    await send(deps, envelope_body())

    parents = [
        call for call in deps.client.calls_named("create_issue")
        if call["parent_id"] is None
    ]
    assert len(parents) == 1


async def test_pending_parent_ignores_a_different_team(deps):
    """A project+context can have a separate parent per Linear team; the
    project-uuid and context footers alone are not enough to adopt across
    teams, since neither carries team identity."""
    with deps.session_factory() as session:
        store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        session.commit()
    deps.client.seed_issue(
        description=(
            f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1\nEndor-context-id: main\n"
            f"{PARENT_TEAM_FOOTER_PREFIX} sec"
        ),
        identifier="SEC-7",
    )

    await send(deps, envelope_body())

    parents = [
        call for call in deps.client.calls_named("create_issue")
        if call["parent_id"] is None
    ]
    assert len(parents) == 1
    with deps.session_factory() as session:
        parent, _ = store.get_or_create_pending_parent(
            session, project_uuid="proj-1", context_id="main", team_key="plat"
        )
        assert parent.linear_identifier != "SEC-7"


async def test_find_parent_issue_rejects_a_candidate_missing_the_project_footer():
    """The search term itself must be re-verified, not assumed from the query.

    FakeLinearClient.search_issues already filters by the query substring, so
    this exercises _find_parent_issue directly against a client double that
    returns a candidate regardless of content -- standing in for Linear's real
    full-text search, which may be fuzzier than an exact substring match.
    """
    from endor_linear_bridge.handlers import _find_parent_issue

    class LooseSearchClient(FakeLinearClient):
        async def search_issues(self, query, first=10):
            self.calls.append(("search_issues", {"query": query}))
            return [
                {
                    "id": "bad-1",
                    "identifier": "PLAT-9",
                    # Has the context and team footers, but not the project one.
                    "description": (
                        f"Endor-context-id: main\n{PARENT_TEAM_FOOTER_PREFIX} plat"
                    ),
                }
            ]

    deps = HandlerDeps(
        session_factory=None,
        client=LooseSearchClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )
    envelope = parse_envelope(envelope_body())

    result = await _find_parent_issue(deps, RUNTIME, envelope)

    assert result is None


async def test_linear_request_error_becomes_transient_failure(deps):
    """A Linear 4xx is a config problem; we still return 503 so Endor retries."""
    deps.client.fail_next["create_issue"] = LinearRequestError("bad state id")

    with pytest.raises(TransientFailure):
        await send(deps, envelope_body())


async def test_failed_open_does_not_record_the_ledger(deps):
    body = envelope_body()
    deps.client.fail_next["create_issue"] = LinearTransientError("nope")

    with pytest.raises(TransientFailure):
        await send(deps, body)

    with deps.session_factory() as session:
        assert not store.ledger_has(
            session, "notif-1", "open", store.payload_hash(body)
        )


async def test_no_deps_sentinel_titles_the_sub_issue(deps):
    body = envelope_body(target="__ENDOR_FINDINGS_WITH_NO_DEPS__")

    await send(deps, body)

    sub_issue = deps.client.calls_named("create_issue")[1]
    assert sub_issue["title"] == "Findings with no dependencies"


async def test_unknown_team_key_raises_key_error(deps):
    """app.py rejects unknown teams with 404 before reaching the handler."""
    body = envelope_body()
    with pytest.raises(KeyError):
        await handle_event(deps, "nope", parse_envelope(body), body)


async def test_created_sub_issue_log_carries_notification_uuid_and_identifier(
    deps, caplog
):
    """Fix 4 / spec section 11: every lifecycle log line must be greppable by
    notification_uuid, and a created-or-updated issue must log its Linear
    identifier (linear_identifier, promoted to a top-level JSON key by
    app.py's JsonLogFormatter) since the workspace slug needed to log a full
    Linear URL is not available to this service."""
    import logging

    with caplog.at_level(logging.INFO, logger="endor_linear_bridge.handlers"):
        await send(deps, envelope_body())

    records = [r for r in caplog.records if "created sub-issue" in r.message]
    assert records
    assert records[0].notification_uuid == "notif-1"
    assert records[0].team_key == "plat"
    assert records[0].event == "open"
    assert records[0].linear_identifier == "PLAT-2"
