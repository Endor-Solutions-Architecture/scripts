"""Startup synchronization with Linear.

Resolves configured team keys to team ids, picks workflow state ids by type
(honoring name overrides), and ensures every configured and severity label
exists. The result is one immutable TeamRuntime per configured team; handlers
read ids from it and never query for them per request.

Linear has no transition graph -- closing an issue is just setting any
completed-type state -- so the Jira plugin's "find a legal transition" problem
does not exist here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from endor_linear_bridge.config import Config, TeamConfig
from endor_linear_bridge.linear_client import LinearClient
from endor_linear_bridge.severity import (
    CRITICAL,
    HIGH,
    LOW,
    MEDIUM,
    PRIORITY_NONE,
    label_word,
    priority_for,
)

TYPE_UNSTARTED = "unstarted"
TYPE_COMPLETED = "completed"

ALL_SEVERITIES = (CRITICAL, HIGH, MEDIUM, LOW)


class StartupError(Exception):
    """Raised when Linear cannot satisfy the configured teams, states, or labels."""


@dataclass(frozen=True)
class TeamRuntime:
    config: TeamConfig
    linear_team_id: str
    open_state_id: str
    close_state_id: str
    reopen_state_id: str
    base_label_ids: tuple[str, ...]
    severity_label_ids: dict[str, str]

    def label_ids_for(self, severity: str) -> tuple[str, ...]:
        """The complete label set for an issue at this severity.

        Linear treats labelIds as a full replacement, so this always returns
        every label the issue should have -- never a delta.
        """
        word = label_word(severity)
        severity_id = self.severity_label_ids.get(word) if word else None
        if severity_id:
            return self.base_label_ids + (severity_id,)
        return self.base_label_ids

    def priority_for_severity(self, severity: str) -> int:
        """Priority honoring the team's priority_from_severity setting."""
        if not self.config.priority_from_severity:
            return PRIORITY_NONE
        return priority_for(severity)


def pick_state(
    states: Sequence[dict],
    *,
    override_name: str | None,
    wanted_type: str,
    team_key: str,
    purpose: str,
) -> str:
    """Resolve a workflow state id by name override, else by state type."""
    if override_name:
        for state in states:
            if state["name"].casefold() == override_name.casefold():
                return state["id"]
        available = ", ".join(sorted(state["name"] for state in states))
        raise StartupError(
            f"team '{team_key}': {purpose} '{override_name}' is not a workflow "
            f"state on this team (available: {available})"
        )

    for state in states:
        if state["type"] == wanted_type:
            return state["id"]

    raise StartupError(
        f"team '{team_key}': no workflow state of type '{wanted_type}' exists, "
        f"so {purpose} cannot be resolved -- set it explicitly in config.yaml"
    )


async def _ensure_labels(
    client: LinearClient, team_id: str, wanted: Sequence[str]
) -> dict[str, str]:
    """Return name -> id for every wanted label, creating any that are missing."""
    if not wanted:
        return {}

    existing = {
        label["name"].casefold(): label["id"]
        for label in await client.issue_labels(team_id)
    }

    resolved: dict[str, str] = {}
    for name in wanted:
        found = existing.get(name.casefold())
        if found is None:
            created = await client.create_issue_label(team_id, name)
            found = created["id"]
            existing[name.casefold()] = found
        resolved[name] = found
    return resolved


async def build_team_runtimes(
    client: LinearClient, config: Config
) -> dict[str, TeamRuntime]:
    """Resolve every configured team against Linear. Raises StartupError on any gap."""
    teams_by_key = {team["key"]: team for team in await client.teams()}

    runtimes: dict[str, TeamRuntime] = {}
    for team_key, team_config in config.teams.items():
        linear_team = teams_by_key.get(team_config.linear_team_key)
        if linear_team is None:
            available = ", ".join(sorted(teams_by_key)) or "(none visible)"
            raise StartupError(
                f"team '{team_key}': Linear team key "
                f"'{team_config.linear_team_key}' not found (available: {available})"
            )

        team_id = linear_team["id"]
        states = await client.workflow_states(team_id)

        open_state_id = pick_state(
            states,
            override_name=team_config.open_state,
            wanted_type=TYPE_UNSTARTED,
            team_key=team_key,
            purpose="open_state",
        )
        close_state_id = pick_state(
            states,
            override_name=team_config.close_state,
            wanted_type=TYPE_COMPLETED,
            team_key=team_key,
            purpose="close_state",
        )
        if team_config.reopen_state:
            reopen_state_id = pick_state(
                states,
                override_name=team_config.reopen_state,
                wanted_type=TYPE_UNSTARTED,
                team_key=team_key,
                purpose="reopen_state",
            )
        else:
            reopen_state_id = open_state_id

        severity_names = (
            [
                f"{team_config.severity_label_prefix}{label_word(severity)}"
                for severity in ALL_SEVERITIES
            ]
            if team_config.severity_labels
            else []
        )
        label_ids = await _ensure_labels(
            client, team_id, list(team_config.labels) + severity_names
        )

        severity_label_ids = {}
        if team_config.severity_labels:
            for severity in ALL_SEVERITIES:
                word = label_word(severity)
                name = f"{team_config.severity_label_prefix}{word}"
                severity_label_ids[word] = label_ids[name]

        runtimes[team_key] = TeamRuntime(
            config=team_config,
            linear_team_id=team_id,
            open_state_id=open_state_id,
            close_state_id=close_state_id,
            reopen_state_id=reopen_state_id,
            base_label_ids=tuple(
                label_ids[name] for name in team_config.labels
            ),
            severity_label_ids=severity_label_ids,
        )

    return runtimes
