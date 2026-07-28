"""Lifecycle orchestration for Endor notification events.

This module contains no SQL and no GraphQL -- it composes store.py and
linear_client.py. Two invariants drive the design:

1. Issue content always renders from the finding rows in the database, never
   from a single webhook payload. Endor's UPDATE payloads carry only NEW
   findings, so rendering from the payload would erase earlier ones.

2. Every Linear issue creation is two-phase: a pending row is written first,
   the Linear call happens second, the ids are attached third. A retry that
   finds a pending row searches Linear for the recovery footer and adopts the
   existing issue rather than creating a duplicate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy.orm import Session

from endor_linear_bridge import render, store
from endor_linear_bridge.config import Config
from endor_linear_bridge.envelope import Envelope
from endor_linear_bridge.linear_cache import TeamRuntime
from endor_linear_bridge.linear_client import LinearError
from endor_linear_bridge.models import (
    STATUS_PENDING,
    STATUS_RESOLVED,
    NotificationIssue,
    ProjectParent,
)
from endor_linear_bridge.severity import max_severity

logger = logging.getLogger(__name__)


class TransientFailure(Exception):
    """The event could not be processed now. app.py maps this to HTTP 503."""


@dataclass(frozen=True)
class HandlerDeps:
    session_factory: Any
    client: Any
    runtimes: dict[str, TeamRuntime]
    config: Config


async def handle_event(
    deps: HandlerDeps, team_key: str, envelope: Envelope, raw_body: bytes
) -> None:
    """Dispatch a validated envelope to its lifecycle handler.

    Raises KeyError for an unknown team key -- app.py checks the team before
    calling, so reaching here with an unknown key is a programming error.
    """
    if team_key not in deps.runtimes:
        raise KeyError(f"unknown team key: {team_key}")

    if envelope.event == "open":
        await handle_open(deps, team_key, envelope, raw_body)
    elif envelope.event == "update":
        await handle_update(deps, team_key, envelope, raw_body)
    elif envelope.event == "resolve":
        await handle_resolve(deps, team_key, envelope, raw_body)
    else:  # pragma: no cover -- envelope validation restricts the values
        raise ValueError(f"unsupported event: {envelope.event}")


async def handle_update(
    deps: HandlerDeps, team_key: str, envelope: Envelope, raw_body: bytes
) -> None:
    runtime = deps.runtimes[team_key]
    notification = envelope.notification
    body_hash = store.payload_hash(raw_body)

    # Decide whether this notification is known before opening a write session,
    # so the create-instead fallback does not nest two sessions on one database.
    with deps.session_factory() as session:
        if store.ledger_has(session, notification.uuid, "update", body_hash):
            logger.info(
                "duplicate update delivery ignored",
                extra=_log_context(team_key, envelope),
            )
            return
        row = store.get_notification(session, notification.uuid)
        is_known = row is not None and row.linear_issue_id is not None

    if not is_known:
        # Never seen this notification (out-of-order delivery, or the database
        # was lost). Create the issue from what we have; the description
        # completes on the next open or update.
        logger.warning(
            "update for unknown notification -- creating instead",
            extra=_log_context(team_key, envelope),
        )
        await handle_open(deps, team_key, envelope, raw_body)
        # handle_open ledgers under "open"; also claim the "update" key so a
        # redelivery of this same body is a no-op rather than a duplicate
        # comment. If handle_open raised (TransientFailure), we never reach
        # here, so the ledger entry is correctly withheld and Endor retries.
        with deps.session_factory() as session:
            store.record_event(session, notification.uuid, "update", body_hash)
            session.commit()
        return

    try:
        with deps.session_factory() as session:
            row = store.get_notification(session, notification.uuid)

            # The payload holds only NEW findings, so merge rather than replace.
            await _apply_current_state(
                deps, session, runtime, envelope, row, replace=False
            )

            if envelope.findings:
                await deps.client.create_comment(
                    row.linear_issue_id, render.update_comment(envelope.findings)
                )

            store.record_event(session, notification.uuid, "update", body_hash)
            session.commit()

    except LinearError as exc:
        raise TransientFailure(f"Linear call failed: {exc}") from exc


async def handle_resolve(
    deps: HandlerDeps, team_key: str, envelope: Envelope, raw_body: bytes
) -> None:
    runtime = deps.runtimes[team_key]
    notification = envelope.notification
    body_hash = store.payload_hash(raw_body)

    try:
        with deps.session_factory() as session:
            if store.ledger_has(session, notification.uuid, "resolve", body_hash):
                logger.info(
                    "duplicate resolve delivery ignored",
                    extra=_log_context(team_key, envelope),
                )
                return

            row = store.get_notification(session, notification.uuid)

            if row is None or row.status == STATUS_RESOLVED:
                # Nothing to close. Record the event and return 200 -- a 4xx here
                # would make Endor mark the whole target as misconfigured.
                logger.warning(
                    "resolve for unknown or already-resolved notification",
                    extra=_log_context(team_key, envelope),
                )
                store.record_event(session, notification.uuid, "resolve", body_hash)
                session.commit()
                return

            await deps.client.update_issue(
                row.linear_issue_id, state_id=runtime.close_state_id
            )
            await deps.client.create_comment(
                row.linear_issue_id,
                render.resolution_comment(datetime.now(timezone.utc)),
            )
            store.mark_resolved(session, row)
            logger.info(
                "resolved sub-issue %s",
                row.linear_identifier,
                extra=_log_context(
                    team_key, envelope, linear_identifier=row.linear_identifier
                ),
            )

            remaining = store.count_unresolved_siblings(
                session, row.parent_id, notification.uuid
            )
            if remaining == 0:
                parent = session.get(ProjectParent, row.parent_id)
                if parent is not None and parent.status != STATUS_RESOLVED:
                    await deps.client.update_issue(
                        parent.linear_issue_id, state_id=runtime.close_state_id
                    )
                    await deps.client.create_comment(
                        parent.linear_issue_id,
                        render.parent_resolution_comment(datetime.now(timezone.utc)),
                    )
                    store.mark_resolved(session, parent)
                    logger.info(
                        "resolved parent issue %s",
                        parent.linear_identifier,
                        extra=_log_context(
                            team_key,
                            envelope,
                            linear_identifier=parent.linear_identifier,
                        ),
                    )

            store.record_event(session, notification.uuid, "resolve", body_hash)
            session.commit()

    except LinearError as exc:
        raise TransientFailure(f"Linear call failed: {exc}") from exc


def _log_context(
    team_key: str, envelope: Envelope, *, linear_identifier: str | None = None
) -> dict[str, str]:
    context = {
        "team_key": team_key,
        "event": envelope.event,
        "notification_uuid": envelope.notification.uuid,
    }
    if linear_identifier is not None:
        context["linear_identifier"] = linear_identifier
    return context


def _description_for(
    deps: HandlerDeps, envelope: Envelope, findings: Sequence[Any]
) -> str:
    notification = envelope.notification
    return render.sub_issue_description(
        notification_uuid=notification.uuid,
        findings=findings,
        project_name=notification.project_name,
        project_app_url=notification.project_app_url,
        policy_name=notification.policy_name,
        policy_app_url=notification.policy_app_url,
        max_findings=deps.config.max_findings_per_issue,
    )


async def ensure_parent(
    deps: HandlerDeps,
    session: Session,
    runtime: TeamRuntime,
    envelope: Envelope,
) -> ProjectParent:
    """Return an open parent issue for this (project, context, team).

    Creates it, adopts an orphan from a previous crashed run, or reopens a
    resolved one -- whichever the stored status calls for.
    """
    notification = envelope.notification
    team_key = runtime.config.key
    parent, _created = store.get_or_create_pending_parent(
        session,
        project_uuid=notification.project_uuid,
        context_id=notification.context_id,
        team_key=team_key,
    )

    if parent.status == STATUS_PENDING:
        if parent.linear_issue_id is None:
            adopted = await _find_parent_issue(deps, runtime, envelope)
            if adopted is not None:
                store.attach_linear_issue(
                    session, parent, adopted["id"], adopted["identifier"]
                )
                logger.info(
                    "adopted existing parent issue %s",
                    adopted["identifier"],
                    extra=_log_context(
                        team_key, envelope, linear_identifier=adopted["identifier"]
                    ),
                )
                return parent

            issue = await deps.client.create_issue(
                team_id=runtime.linear_team_id,
                title=render.parent_title(
                    notification.project_name, notification.ref_name
                ),
                description=render.parent_description(
                    project_uuid=notification.project_uuid,
                    context_id=notification.context_id,
                    team_key=team_key,
                    project_name=notification.project_name,
                    project_app_url=notification.project_app_url,
                    policy_name=notification.policy_name,
                    policy_app_url=notification.policy_app_url,
                ),
                state_id=runtime.open_state_id,
                label_ids=runtime.base_label_ids,
            )
            store.attach_linear_issue(
                session, parent, issue["id"], issue["identifier"]
            )
            logger.info(
                "created parent issue %s",
                issue["identifier"],
                extra=_log_context(
                    team_key, envelope, linear_identifier=issue["identifier"]
                ),
            )
        # A PENDING parent with linear_issue_id already set cannot occur --
        # attach_linear_issue() always sets status OPEN alongside the id, so
        # there is no state transition that leaves the two disagreeing.
        return parent

    if parent.status == STATUS_RESOLVED:
        await deps.client.update_issue(
            parent.linear_issue_id, state_id=runtime.reopen_state_id
        )
        await deps.client.create_comment(
            parent.linear_issue_id, render.reopen_comment()
        )
        store.mark_open(session, parent)
        logger.info(
            "reopened parent issue %s",
            parent.linear_identifier,
            extra=_log_context(
                team_key, envelope, linear_identifier=parent.linear_identifier
            ),
        )

    return parent


async def _find_parent_issue(
    deps: HandlerDeps, runtime: TeamRuntime, envelope: Envelope
) -> dict[str, Any] | None:
    """Search Linear for a parent issue left behind by a crashed run.

    The search term alone is too broad to adopt on: it is confirmed against
    all three footers -- project, context, and team -- since a project can
    have a separate parent issue per Linear team and Linear's real search may
    be fuzzier than an exact substring match.
    """
    notification = envelope.notification
    query = render.parent_footer_query(notification.project_uuid)
    context_footer = render.parent_context_footer(notification.context_id)
    team_footer = render.parent_team_footer(runtime.config.key)

    for candidate in await deps.client.search_issues(query):
        description = candidate.get("description") or ""
        if (
            query in description
            and context_footer in description
            and team_footer in description
        ):
            return candidate
    return None


async def _find_sub_issue(
    deps: HandlerDeps, notification_uuid: str
) -> dict[str, Any] | None:
    """Search Linear for a sub-issue left behind by a crashed run."""
    query = render.notification_footer_query(notification_uuid)
    for candidate in await deps.client.search_issues(query):
        if query in (candidate.get("description") or ""):
            return candidate
    return None


async def handle_open(
    deps: HandlerDeps, team_key: str, envelope: Envelope, raw_body: bytes
) -> None:
    runtime = deps.runtimes[team_key]
    notification = envelope.notification
    body_hash = store.payload_hash(raw_body)

    try:
        with deps.session_factory() as session:
            if store.ledger_has(session, notification.uuid, "open", body_hash):
                logger.info(
                    "duplicate open delivery ignored",
                    extra=_log_context(team_key, envelope),
                )
                return

            existing = store.get_notification(session, notification.uuid)

            if existing is not None and existing.status != STATUS_PENDING:
                # A resent OPEN for a notification we already track. Its payload
                # is complete, so replace the stored set rather than merging.
                await _apply_current_state(
                    deps, session, runtime, envelope, existing, replace=True
                )
                store.record_event(session, notification.uuid, "open", body_hash)
                session.commit()
                return

            parent = await ensure_parent(deps, session, runtime, envelope)

            row = existing or store.create_pending_notification(
                session,
                notification_uuid=notification.uuid,
                team_key=team_key,
                parent_id=parent.id,
                aggregation_target=notification.aggregation.target_name,
            )

            store.replace_findings(session, notification.uuid, envelope.findings)
            findings = store.all_findings(session, notification.uuid)
            severity = max_severity([f.severity for f in findings])

            if row.linear_issue_id is None:
                adopted = await _find_sub_issue(deps, notification.uuid)
                if adopted is not None:
                    store.attach_linear_issue(
                        session, row, adopted["id"], adopted["identifier"]
                    )
                    logger.info(
                        "adopted existing sub-issue %s",
                        adopted["identifier"],
                        extra=_log_context(
                            team_key, envelope, linear_identifier=adopted["identifier"]
                        ),
                    )
                    await deps.client.update_issue(
                        adopted["id"],
                        description=_description_for(deps, envelope, findings),
                        priority=runtime.priority_for_severity(severity),
                        label_ids=runtime.label_ids_for(severity),
                    )
                else:
                    issue = await deps.client.create_issue(
                        team_id=runtime.linear_team_id,
                        title=render.sub_issue_title(
                            notification.aggregation.target_name
                        ),
                        description=_description_for(deps, envelope, findings),
                        parent_id=parent.linear_issue_id,
                        state_id=runtime.open_state_id,
                        priority=runtime.priority_for_severity(severity),
                        label_ids=runtime.label_ids_for(severity),
                    )
                    store.attach_linear_issue(
                        session, row, issue["id"], issue["identifier"]
                    )
                    logger.info(
                        "created sub-issue %s",
                        issue["identifier"],
                        extra=_log_context(
                            team_key, envelope, linear_identifier=issue["identifier"]
                        ),
                    )

            store.record_event(session, notification.uuid, "open", body_hash)
            session.commit()

    except LinearError as exc:
        raise TransientFailure(f"Linear call failed: {exc}") from exc


async def _apply_current_state(
    deps: HandlerDeps,
    session: Session,
    runtime: TeamRuntime,
    envelope: Envelope,
    row: NotificationIssue,
    *,
    replace: bool,
) -> None:
    """Rewrite an existing sub-issue from the stored finding union.

    `replace` distinguishes OPEN (payload is the complete set) from UPDATE
    (payload holds only new findings, so merge). Task 9 reuses this.

    Invariant: a parent is open iff it has at least one unresolved child. So a
    row transitioning out of `resolved` here must also ensure its parent is
    open -- reusing ensure_parent(), which is a no-op when the parent is
    already open and reopens it (with its own comment) when it is resolved.
    Without this, a sub-issue reopened by a retried UPDATE that arrives after
    a RESOLVE closed both the sub-issue and its (now childless) parent would
    leave the parent closed forever, since count_unresolved_siblings() would
    then always report at least one unresolved child.
    """
    notification = envelope.notification

    if replace:
        store.replace_findings(session, notification.uuid, envelope.findings)
    else:
        store.upsert_findings(session, notification.uuid, envelope.findings)

    findings = store.all_findings(session, notification.uuid)
    severity = max_severity([f.severity for f in findings])

    if row.status == STATUS_RESOLVED:
        store.mark_open(session, row)
        await deps.client.update_issue(
            row.linear_issue_id, state_id=runtime.reopen_state_id
        )
        await deps.client.create_comment(row.linear_issue_id, render.reopen_comment())
        await ensure_parent(deps, session, runtime, envelope)

    await deps.client.update_issue(
        row.linear_issue_id,
        description=_description_for(deps, envelope, findings),
        priority=runtime.priority_for_severity(severity),
        label_ids=runtime.label_ids_for(severity),
    )
