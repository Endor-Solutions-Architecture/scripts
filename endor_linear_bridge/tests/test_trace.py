"""The per-request trace collector behind the dashboard's delivery drawer."""

import asyncio

from endor_linear_bridge import trace


def test_step_outside_a_request_is_a_noop():
    # CLI replays and unit tests call handlers without begin(); steps must
    # neither crash nor leak into some global list.
    trace.step("Ledger check", "new payload hash")
    assert trace.steps() == []


def test_begin_collects_steps_in_order():
    trace.begin()
    trace.step("Signature verified", "hmac ok")
    trace.step("Linear call failed", "429", ok=False, kind="linear_error")

    got = trace.steps()
    assert [s["step"] for s in got] == ["Signature verified", "Linear call failed"]
    assert got[0] == {"step": "Signature verified", "detail": "hmac ok", "ok": True}
    assert got[1]["ok"] is False
    assert got[1]["kind"] == "linear_error"


def test_concurrent_requests_do_not_share_a_trace():
    async def request(name: str) -> list[dict]:
        trace.begin()
        trace.step(f"step from {name}")
        await asyncio.sleep(0)
        trace.step(f"second step from {name}")
        return trace.steps()

    async def main():
        return await asyncio.gather(request("a"), request("b"))

    got_a, got_b = asyncio.run(main())
    assert [s["step"] for s in got_a] == ["step from a", "second step from a"]
    assert [s["step"] for s in got_b] == ["step from b", "second step from b"]


def test_has_kind_reports_whether_any_step_matches():
    trace.begin()
    trace.step("Ledger check", "already processed", kind="noop")
    assert trace.has_kind("noop")
    assert not trace.has_kind("issue_created")
