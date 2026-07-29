"""Handlers record trace steps the dashboard drawer replays."""

import asyncio

import pytest

from endor_linear_bridge import trace
from endor_linear_bridge.handlers import HandlerDeps, handle_event
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_handlers_open import (
    CONFIG,
    RUNTIME,
    envelope_body,
)
from endor_linear_bridge.envelope import parse_envelope


@pytest.fixture
def deps(session_factory):
    return HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )


def deliver(deps, body):
    envelope = parse_envelope(body)
    asyncio.run(handle_event(deps, "plat", envelope, body))


def kinds(steps):
    return [s.get("kind") for s in steps if s.get("kind")]


def test_open_happy_path_traces_ledger_findings_and_creation(deps):
    trace.begin()
    deliver(deps, envelope_body())

    got = kinds(trace.steps())
    assert "findings_stored" in got
    assert "parent_created" in got
    assert "issue_created" in got
    # The drawer shows Linear identifiers; the creation step must carry one.
    created = next(s for s in trace.steps() if s.get("kind") == "issue_created")
    assert "PLAT-" in created["detail"]


def test_duplicate_delivery_traces_a_noop(deps):
    body = envelope_body()
    deliver(deps, body)

    trace.begin()
    deliver(deps, body)
    assert trace.has_kind("noop")


def test_resolve_traces_issue_and_parent_close(deps):
    deliver(deps, envelope_body())

    trace.begin()
    deliver(deps, envelope_body(event="resolve", findings=()))
    got = kinds(trace.steps())
    assert "issue_closed" in got
    assert "parent_closed" in got
