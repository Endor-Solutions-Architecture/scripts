"""SQLAlchemy tables for the bridge's state.

This database is the only mapping from Endor notification UUID to Linear
issue. It is small, but losing it orphans open tickets -- see the recovery
footers in render.py and the adoption path in handlers.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm import Session

STATUS_PENDING = "pending"
STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"

UNRESOLVED_STATUSES = (STATUS_PENDING, STATUS_OPEN)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectParent(Base):
    __tablename__ = "project_parents"
    __table_args__ = (
        UniqueConstraint("project_uuid", "context_id", "team_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_uuid: Mapped[str] = mapped_column(String(128), nullable=False)
    context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    team_key: Mapped[str] = mapped_column(String(128), nullable=False)
    linear_issue_id: Mapped[str | None] = mapped_column(String(128))
    linear_identifier: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationIssue(Base):
    __tablename__ = "notification_issues"

    notification_uuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    team_key: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_parents.id"), nullable=False
    )
    aggregation_target: Mapped[str] = mapped_column(String(512), nullable=False)
    linear_issue_id: Mapped[str | None] = mapped_column(String(128))
    linear_identifier: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationFinding(Base):
    __tablename__ = "notification_findings"

    notification_uuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    finding_uuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    severity: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    dependency: Mapped[str | None] = mapped_column(String(512))
    package: Mapped[str | None] = mapped_column(String(512))
    finding_url: Mapped[str | None] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def uuid(self) -> str:
        """Alias so this row satisfies render.FindingLike alongside envelope.Finding."""
        return self.finding_uuid


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    notification_uuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    event: Mapped[str] = mapped_column(String(16), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeliveryLog(Base):
    """One row per webhook the bridge accepted or rejected.

    Written after the handler resolves, including for rejections -- a
    delivery rejected before parse has no notification UUID or target, only
    the team from the route, the outcome, and the failure reason. This table
    exists solely for the /dashboard Deliveries view; nothing in the webhook
    pipeline reads it back.
    """

    __tablename__ = "delivery_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    team: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(16))
    notification_uuid: Mapped[str | None] = mapped_column(String(128))
    target: Mapped[str | None] = mapped_column(String(512))
    project: Mapped[str | None] = mapped_column(String(512))
    branch: Mapped[str | None] = mapped_column(String(255))
    findings_new: Mapped[int | None] = mapped_column(Integer)
    findings_total: Mapped[int | None] = mapped_column(Integer)
    linear_identifier: Mapped[str | None] = mapped_column(String(64))
    linear_action: Mapped[str | None] = mapped_column(String(16))
    parent_identifier: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    trace: Mapped[list | None] = mapped_column(JSON)


def build_engine(database_url: str) -> Engine:
    """Create an engine, enabling WAL mode for SQLite so concurrent reads work."""
    engine = create_engine(database_url, future=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)
