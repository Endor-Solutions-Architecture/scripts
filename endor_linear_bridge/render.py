"""Markdown rendering for Linear issue bodies and comments.

Every function here is pure. Callers pass finding rows -- either
envelope.Finding objects or models.NotificationFinding rows -- and get a
string back. The recovery footers embedded in descriptions are what makes the
issueSearch adoption path in handlers.py possible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from endor_linear_bridge.envelope import NO_DEPS_SENTINEL
from endor_linear_bridge.severity import label_word, sort_key

NOTIFICATION_FOOTER_PREFIX = "Endor-notification-uuid:"
PARENT_PROJECT_FOOTER_PREFIX = "Endor-project-uuid:"
PARENT_CONTEXT_FOOTER_PREFIX = "Endor-context-id:"
PARENT_TEAM_FOOTER_PREFIX = "Endor-team-key:"

NO_DEPS_TITLE = "Findings with no dependencies"


class FindingLike(Protocol):
    """Structural type shared by envelope.Finding and models.NotificationFinding."""

    uuid: str
    severity: str
    description: str
    finding_url: str | None


def _cell(text: str) -> str:
    """Escape a value for use inside a Markdown table cell."""
    return (text or "").replace("|", r"\|").replace("\n", " ").strip()


def _severity_text(severity: str) -> str:
    word = label_word(severity)
    return word.capitalize() if word else "Unspecified"


def _finding_row(finding: FindingLike) -> str:
    description = _cell(finding.description) or "(no description)"
    if finding.finding_url:
        link = f"[View]({finding.finding_url})"
    else:
        link = "—"
    return f"| {_severity_text(finding.severity)} | {description} | {link} |"


def sub_issue_title(aggregation_target: str) -> str:
    if not aggregation_target or aggregation_target == NO_DEPS_SENTINEL:
        return NO_DEPS_TITLE
    return f"[Dep] {aggregation_target}"


def parent_title(project_name: str, ref_name: str) -> str:
    if ref_name:
        return f"[Endor Labs] {project_name} — {ref_name}"
    return f"[Endor Labs] {project_name}"


def _links_section(
    project_name: str, project_app_url: str, policy_name: str, policy_app_url: str
) -> list[str]:
    lines = []
    if project_app_url:
        lines.append(f"- Project: [{project_name or 'project'}]({project_app_url})")
    elif project_name:
        lines.append(f"- Project: {project_name}")
    if policy_name and policy_app_url:
        lines.append(f"- Policy: [{policy_name}]({policy_app_url})")
    elif policy_name:
        lines.append(f"- Policy: {policy_name}")
    return lines


def sub_issue_description(
    *,
    notification_uuid: str,
    findings: Sequence[FindingLike],
    project_name: str,
    project_app_url: str,
    policy_name: str,
    policy_app_url: str,
    max_findings: int,
) -> str:
    ordered = sorted(findings, key=lambda f: sort_key(f.severity))
    shown = ordered[:max_findings]
    hidden = len(ordered) - len(shown)

    lines = ["## Findings reported by Endor Labs", ""]

    if shown:
        lines += ["| Severity | Description | Link |", "| --- | --- | --- |"]
        lines += [_finding_row(f) for f in shown]
        lines.append("")

    if hidden > 0:
        suffix = "finding" if hidden == 1 else "findings"
        if project_app_url:
            lines.append(
                f"_… and {hidden} more {suffix} — "
                f"[view all in Endor Labs]({project_app_url})._"
            )
        else:
            lines.append(f"_… and {hidden} more {suffix} in Endor Labs._")
        lines.append("")

    links = _links_section(project_name, project_app_url, policy_name, policy_app_url)
    if links:
        lines += links + [""]

    lines += ["---", f"{NOTIFICATION_FOOTER_PREFIX} {notification_uuid}"]
    return "\n".join(lines)


def parent_description(
    *,
    project_uuid: str,
    context_id: str,
    team_key: str,
    project_name: str,
    project_app_url: str,
    policy_name: str,
    policy_app_url: str,
) -> str:
    lines = [
        "Tracking issue for Endor Labs findings in this project.",
        "",
        "Each sub-issue covers one dependency with findings. This issue closes "
        "automatically when every sub-issue is resolved.",
        "",
    ]

    links = _links_section(project_name, project_app_url, policy_name, policy_app_url)
    if links:
        lines += links + [""]

    lines += [
        "---",
        f"{PARENT_PROJECT_FOOTER_PREFIX} {project_uuid}",
        f"{PARENT_CONTEXT_FOOTER_PREFIX} {context_id}",
        parent_team_footer(team_key),
    ]
    return "\n".join(lines)


def update_comment(findings: Sequence[FindingLike]) -> str:
    count = len(findings)
    noun = "finding" if count == 1 else "findings"
    lines = [f"**{count} new {noun}** from the latest Endor Labs scan:", ""]

    for finding in sorted(findings, key=lambda f: sort_key(f.severity)):
        description = _cell(finding.description) or "(no description)"
        entry = f"- **{_severity_text(finding.severity)}** — {description}"
        if finding.finding_url:
            entry += f" ([view]({finding.finding_url}))"
        lines.append(entry)

    return "\n".join(lines)


def resolution_comment(timestamp: datetime) -> str:
    stamp = timestamp.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Resolved automatically by an Endor Labs scan on {stamp} — "
        "all findings for this dependency are resolved."
    )


def parent_resolution_comment(timestamp: datetime) -> str:
    """Comment for closing the parent tracking issue.

    Distinct wording from resolution_comment(): that one says "this dependency",
    which is wrong on the parent -- the parent closes because every sub-issue
    (dependency) underneath it resolved, not because the parent itself is a
    dependency.
    """
    stamp = timestamp.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Resolved automatically by an Endor Labs scan on {stamp} — "
        "all sub-issues for this project are resolved."
    )


def reopen_comment() -> str:
    return "New findings reported by Endor Labs — reopening."


def notification_footer_query(notification_uuid: str) -> str:
    return f"{NOTIFICATION_FOOTER_PREFIX} {notification_uuid}"


def parent_footer_query(project_uuid: str) -> str:
    """Search text for finding a parent issue. Project uuid alone is enough to
    search on; the caller confirms the context with parent_context_footer()."""
    return f"{PARENT_PROJECT_FOOTER_PREFIX} {project_uuid}"


def parent_context_footer(context_id: str) -> str:
    """Exact footer line a candidate parent's description must contain."""
    return f"{PARENT_CONTEXT_FOOTER_PREFIX} {context_id}"


def parent_team_footer(team_key: str) -> str:
    """Exact footer line a candidate parent's description must contain.

    Neither the project-uuid nor context footers carry team identity, but a
    project can have a separate parent issue per Linear team -- without this,
    crash-recovery search could adopt another team's parent.
    """
    return f"{PARENT_TEAM_FOOTER_PREFIX} {team_key}"
