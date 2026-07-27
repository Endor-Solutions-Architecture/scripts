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
    raise NotImplementedError("implemented in Task 9")


async def handle_resolve(
    deps: HandlerDeps, team_key: str, envelope: Envelope, raw_body: bytes
) -> None:
    raise NotImplementedError("implemented in Task 9")


def _log_context(team_key: str, envelope: Envelope) -> dict[str, str]:
    return {
        "team_key": team_key,
        "event": envelope.event,
        "notification_uuid": envelope.notification.uuid,
    }


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
    parent, _created = store.get_or_create_pending_parent(
        session,
        project_uuid=notification.project_uuid,
        context_id=notification.context_id,
        team_key=runtime.config.key,
    )

    if parent.status == STATUS_PENDING:
        if parent.linear_issue_id is None:
            adopted = await _find_parent_issue(deps, envelope)
            if adopted is not None:
                store.attach_linear_issue(
                    session, parent, adopted["id"], adopted["identifier"]
                )
                logger.info("adopted existing parent issue %s", adopted["identifier"])
                return parent

            issue = await deps.client.create_issue(
                team_id=runtime.linear_team_id,
                title=render.parent_title(
                    notification.project_name, notification.ref_name
                ),
                description=render.parent_description(
                    project_uuid=notification.project_uuid,
                    context_id=notification.context_id,
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
            logger.info("created parent issue %s", issue["identifier"])
        else:
            store.mark_open(session, parent)
        return parent

    if parent.status == STATUS_RESOLVED:
        await deps.client.update_issue(
            parent.linear_issue_id, state_id=runtime.reopen_state_id
        )
        await deps.client.create_comment(
            parent.linear_issue_id, render.reopen_comment()
        )
        store.mark_open(session, parent)
        logger.info("reopened parent issue %s", parent.linear_identifier)

    return parent


async def _find_parent_issue(
    deps: HandlerDeps, envelope: Envelope
) -> dict[str, Any] | None:
    """Search Linear for a parent issue left behind by a crashed run."""
    notification = envelope.notification
    query = render.parent_footer_query(notification.project_uuid)
    context_footer = render.parent_context_footer(notification.context_id)

    for candidate in await deps.client.search_issues(query):
        if context_footer in (candidate.get("description") or ""):
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
                logger.info("duplicate open delivery ignored", extra=_log_context(team_key, envelope))
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
                        "adopted existing sub-issue %s", adopted["identifier"]
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
                    logger.info("created sub-issue %s", issue["identifier"])

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

    await deps.client.update_issue(
        row.linear_issue_id,
        description=_description_for(deps, envelope, findings),
        priority=runtime.priority_for_severity(severity),
        label_ids=runtime.label_ids_for(severity),
    )
