"""Per-request trace collection for the dashboard's delivery drawer.

app.py calls begin() at the top of each webhook request; the handlers record
what they do with step(). The collected list is stored verbatim in the
delivery_log row, so the drawer replays exactly what happened rather than
reconstructing it at read time.

Built on a ContextVar so concurrent requests (separate asyncio tasks) each
see their own list, and so step() is a safe no-op anywhere the collector was
never started -- unit tests and CLI replays call handlers directly.
"""

from __future__ import annotations

from contextvars import ContextVar

_steps: ContextVar[list[dict] | None] = ContextVar("delivery_trace", default=None)


def begin() -> None:
    """Start a fresh trace for the current task."""
    _steps.set([])


def step(label: str, detail: str = "", *, ok: bool = True, kind: str | None = None) -> None:
    """Record one step. `kind` is a machine-readable tag app.py aggregates on."""
    current = _steps.get()
    if current is None:
        return
    entry: dict = {"step": label, "detail": detail, "ok": ok}
    if kind is not None:
        entry["kind"] = kind
    current.append(entry)


def steps() -> list[dict]:
    return _steps.get() or []


def has_kind(kind: str) -> bool:
    return any(s.get("kind") == kind for s in steps())
