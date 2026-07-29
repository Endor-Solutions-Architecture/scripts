"""All SQL for the bridge lives here.

Handlers call these functions and never touch the ORM directly. Every function
takes an open Session and only flushes; the caller owns the transaction
boundary. handlers.py commits at deliberate points mid-request (the A2
durability points: pending rows before the first Linear call, Linear ids the
moment they are attached) and once at the end for everything else.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from endor_linear_bridge.models import (
    STATUS_OPEN,
    STATUS_PENDING,
    STATUS_RESOLVED,
    UNRESOLVED_STATUSES,
    DeliveryLog,
    NotificationFinding,
    NotificationIssue,
    ProcessedEvent,
    ProjectParent,
    utcnow,
)
from endor_linear_bridge.render import FindingLike


def payload_hash(raw_body: bytes) -> str:
    """sha256 hex of the raw request body -- the ledger's third key component."""
    return hashlib.sha256(raw_body).hexdigest()


def ledger_has(
    session: Session, notification_uuid: str, event: str, payload_hash_value: str
) -> bool:
    stmt = select(ProcessedEvent).where(
        ProcessedEvent.notification_uuid == notification_uuid,
        ProcessedEvent.event == event,
        ProcessedEvent.payload_hash == payload_hash_value,
    )
    return session.execute(stmt).first() is not None


def record_event(
    session: Session, notification_uuid: str, event: str, payload_hash_value: str
) -> None:
    if ledger_has(session, notification_uuid, event, payload_hash_value):
        return
    session.add(
        ProcessedEvent(
            notification_uuid=notification_uuid,
            event=event,
            payload_hash=payload_hash_value,
            processed_at=utcnow(),
        )
    )
    session.flush()


def get_notification(
    session: Session, notification_uuid: str
) -> NotificationIssue | None:
    return session.get(NotificationIssue, notification_uuid)


def create_pending_notification(
    session: Session,
    *,
    notification_uuid: str,
    team_key: str,
    parent_id: int,
    aggregation_target: str,
) -> NotificationIssue:
    now = utcnow()
    row = NotificationIssue(
        notification_uuid=notification_uuid,
        team_key=team_key,
        parent_id=parent_id,
        aggregation_target=aggregation_target,
        status=STATUS_PENDING,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def get_or_create_pending_parent(
    session: Session, *, project_uuid: str, context_id: str, team_key: str
) -> tuple[ProjectParent, bool]:
    """Return (parent, created). A new parent starts pending with no Linear ids."""
    stmt = select(ProjectParent).where(
        ProjectParent.project_uuid == project_uuid,
        ProjectParent.context_id == context_id,
        ProjectParent.team_key == team_key,
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing, False

    now = utcnow()
    parent = ProjectParent(
        project_uuid=project_uuid,
        context_id=context_id,
        team_key=team_key,
        status=STATUS_PENDING,
        created_at=now,
        updated_at=now,
    )
    session.add(parent)
    session.flush()
    return parent, True


def attach_linear_issue(
    session: Session,
    row: ProjectParent | NotificationIssue,
    linear_issue_id: str,
    linear_identifier: str,
) -> None:
    """Record the Linear ids on a pending row and open it. Completes phase two."""
    row.linear_issue_id = linear_issue_id
    row.linear_identifier = linear_identifier
    row.status = STATUS_OPEN
    row.updated_at = utcnow()
    session.flush()


def mark_open(session: Session, row: ProjectParent | NotificationIssue) -> None:
    row.status = STATUS_OPEN
    row.updated_at = utcnow()
    session.flush()


def mark_resolved(session: Session, row: ProjectParent | NotificationIssue) -> None:
    row.status = STATUS_RESOLVED
    row.updated_at = utcnow()
    session.flush()


def _finding_values(finding: FindingLike) -> dict[str, object]:
    return {
        "severity": finding.severity or "",
        "description": finding.description or "",
        "dependency": getattr(finding, "dependency", None),
        "package": getattr(finding, "package", None),
        "finding_url": finding.finding_url,
    }


def replace_findings(
    session: Session, notification_uuid: str, findings: Sequence[FindingLike]
) -> None:
    """Set the stored finding set exactly. Used by OPEN, whose payload is complete."""
    session.execute(
        delete(NotificationFinding).where(
            NotificationFinding.notification_uuid == notification_uuid
        )
    )
    now = utcnow()
    for finding in findings:
        session.add(
            NotificationFinding(
                notification_uuid=notification_uuid,
                finding_uuid=finding.uuid,
                first_seen_at=now,
                **_finding_values(finding),
            )
        )
    session.flush()


def upsert_findings(
    session: Session, notification_uuid: str, findings: Sequence[FindingLike]
) -> int:
    """Merge findings into the stored set, returning how many were new.

    Used by UPDATE, whose payload carries only new findings -- removing absent
    rows here would erase everything reported earlier.
    """
    inserted = 0
    now = utcnow()
    for finding in findings:
        existing = session.get(
            NotificationFinding, (notification_uuid, finding.uuid)
        )
        values = _finding_values(finding)
        if existing is None:
            session.add(
                NotificationFinding(
                    notification_uuid=notification_uuid,
                    finding_uuid=finding.uuid,
                    first_seen_at=now,
                    **values,
                )
            )
            inserted += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
    session.flush()
    return inserted


def all_findings(
    session: Session, notification_uuid: str
) -> list[NotificationFinding]:
    stmt = (
        select(NotificationFinding)
        .where(NotificationFinding.notification_uuid == notification_uuid)
        .order_by(NotificationFinding.finding_uuid)
    )
    return list(session.execute(stmt).scalars())


def record_delivery(session: Session, **fields: object) -> DeliveryLog:
    """Append one row to the delivery log. Caller owns the commit."""
    row = DeliveryLog(received_at=utcnow(), **fields)
    session.add(row)
    session.flush()
    return row


def _delivery_window(stmt, since: datetime | None):
    if since is not None:
        stmt = stmt.where(DeliveryLog.received_at >= since)
    return stmt


def recent_deliveries(
    session: Session,
    *,
    since: datetime | None,
    event_type: str | None = None,
    failed_only: bool = False,
    search: str | None = None,
    limit: int = 200,
) -> list[DeliveryLog]:
    stmt = _delivery_window(select(DeliveryLog), since)
    if event_type is not None:
        stmt = stmt.where(DeliveryLog.event_type == event_type)
    if failed_only:
        stmt = stmt.where(DeliveryLog.outcome.in_(("retrying", "rejected")))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                DeliveryLog.notification_uuid.like(pattern),
                DeliveryLog.target.like(pattern),
                DeliveryLog.linear_identifier.like(pattern),
            )
        )
    stmt = stmt.order_by(DeliveryLog.id.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


def delivery_summary(session: Session, *, since: datetime | None) -> dict[str, int]:
    """Counts by outcome plus the overall total, for the Deliveries summary strip."""
    stmt = _delivery_window(
        select(DeliveryLog.outcome, func.count()).group_by(DeliveryLog.outcome),
        since,
    )
    by_outcome = {outcome: int(n) for outcome, n in session.execute(stmt)}
    return {
        "received": sum(by_outcome.values()),
        "ok": by_outcome.get("ok", 0),
        "noop": by_outcome.get("noop", 0),
        "retrying": by_outcome.get("retrying", 0),
        "rejected": by_outcome.get("rejected", 0),
    }


def team_delivery_stats(
    session: Session, *, since: datetime | None
) -> dict[str, dict[str, object]]:
    """Per-team event counts, failure count, and last event time."""
    stmt = _delivery_window(
        select(
            DeliveryLog.team,
            DeliveryLog.event_type,
            DeliveryLog.outcome,
            func.count(),
            func.max(DeliveryLog.received_at),
        ).group_by(DeliveryLog.team, DeliveryLog.event_type, DeliveryLog.outcome),
        since,
    )
    stats: dict[str, dict[str, object]] = {}
    for team, event_type, outcome, count, last_at in session.execute(stmt):
        entry = stats.setdefault(
            team,
            {"open": 0, "update": 0, "resolve": 0, "failed": 0, "last_event_at": None},
        )
        if event_type in ("open", "update", "resolve"):
            entry[event_type] += int(count)
        if outcome in ("retrying", "rejected"):
            entry["failed"] += int(count)
        if entry["last_event_at"] is None or last_at > entry["last_event_at"]:
            entry["last_event_at"] = last_at
    return stats


def failure_counts(session: Session, *, since: datetime | None) -> dict[str, int]:
    stmt = _delivery_window(
        select(DeliveryLog.failure_reason, func.count())
        .where(DeliveryLog.failure_reason.is_not(None))
        .group_by(DeliveryLog.failure_reason),
        since,
    )
    return {reason: int(n) for reason, n in session.execute(stmt)}


def severity_totals(session: Session) -> dict[str, int]:
    """Finding counts by severity across the whole stored union."""
    stmt = select(NotificationFinding.severity, func.count()).group_by(
        NotificationFinding.severity
    )
    return {severity: int(n) for severity, n in session.execute(stmt)}


def findings_total(session: Session) -> int:
    return int(
        session.execute(select(func.count()).select_from(NotificationFinding))
        .scalar_one()
    )


def issue_counts(session: Session) -> dict[str, dict[str, int]]:
    """Per-team open/closed sub-issue counts. Pending rows count as neither."""
    stmt = select(
        NotificationIssue.team_key, NotificationIssue.status, func.count()
    ).group_by(NotificationIssue.team_key, NotificationIssue.status)
    counts: dict[str, dict[str, int]] = {}
    for team_key, status, n in session.execute(stmt):
        entry = counts.setdefault(team_key, {"open": 0, "closed": 0})
        if status == STATUS_OPEN:
            entry["open"] += int(n)
        elif status == STATUS_RESOLVED:
            entry["closed"] += int(n)
    return counts


def severity_mix(
    session: Session, notification_uuids: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Per-notification finding counts by severity, for the delivery drawer."""
    if not notification_uuids:
        return {}
    stmt = (
        select(
            NotificationFinding.notification_uuid,
            NotificationFinding.severity,
            func.count(),
        )
        .where(NotificationFinding.notification_uuid.in_(notification_uuids))
        .group_by(
            NotificationFinding.notification_uuid, NotificationFinding.severity
        )
    )
    mix: dict[str, dict[str, int]] = {}
    for uuid, severity, n in session.execute(stmt):
        mix.setdefault(uuid, {})[severity] = int(n)
    return mix


def event_times(
    session: Session, *, since: datetime | None
) -> list[tuple[datetime, str]]:
    """(received_at, event_type) for every parsed delivery in the window."""
    stmt = _delivery_window(
        select(DeliveryLog.received_at, DeliveryLog.event_type).where(
            DeliveryLog.event_type.is_not(None)
        ),
        since,
    ).order_by(DeliveryLog.received_at)
    return [(at, event) for at, event in session.execute(stmt)]


def prune_delivery_log(session: Session, *, older_than: datetime) -> int:
    """Delete rows older than the cutoff, returning how many were removed."""
    result = session.execute(
        delete(DeliveryLog).where(DeliveryLog.received_at < older_than)
    )
    session.flush()
    return int(result.rowcount or 0)


def count_unresolved_siblings(
    session: Session, parent_id: int, exclude_uuid: str
) -> int:
    """How many other sub-issues under this parent are still pending or open."""
    stmt = (
        select(func.count())
        .select_from(NotificationIssue)
        .where(
            NotificationIssue.parent_id == parent_id,
            NotificationIssue.notification_uuid != exclude_uuid,
            NotificationIssue.status.in_(UNRESOLVED_STATUSES),
        )
    )
    return int(session.execute(stmt).scalar_one())
