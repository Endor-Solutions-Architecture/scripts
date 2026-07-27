"""All SQL for the bridge lives here.

Handlers call these functions and never touch the ORM directly. Every function
takes an open Session; the caller owns the transaction boundary so a whole
request commits atomically.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from endor_linear_bridge.models import (
    STATUS_OPEN,
    STATUS_PENDING,
    STATUS_RESOLVED,
    UNRESOLVED_STATUSES,
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
