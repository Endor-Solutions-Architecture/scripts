"""Configuration loading for the Endor Linear bridge.

Secrets are never stored in config.yaml -- the file names environment
variables, and this module resolves them. A missing or empty variable is a
startup failure, not a runtime surprise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import os
import yaml

DEFAULT_LINEAR_API_URL = "https://api.linear.app/graphql"
DEFAULT_DATABASE_URL = "sqlite:///./bridge.db"
DEFAULT_MAX_FINDINGS = 50
DEFAULT_SEVERITY_LABEL_PREFIX = "endor-"


class ConfigError(Exception):
    """Raised when the configuration file or its environment is unusable."""


@dataclass(frozen=True)
class TeamConfig:
    key: str
    linear_team_key: str
    hmac_secret: str
    open_state: str | None
    close_state: str | None
    reopen_state: str | None
    labels: tuple[str, ...]
    priority_from_severity: bool
    severity_labels: bool
    severity_label_prefix: str


@dataclass(frozen=True)
class Config:
    linear_api_key: str
    linear_api_url: str
    inbound_bearer_token: str
    database_url: str
    max_findings_per_issue: int
    teams: dict[str, TeamConfig]


def _require_env(env: Mapping[str, str], var_name: str, purpose: str) -> str:
    if not var_name:
        raise ConfigError(f"{purpose} is missing an environment variable name")
    value = env.get(var_name, "")
    if not value:
        raise ConfigError(
            f"environment variable {var_name} ({purpose}) is unset or empty"
        )
    return value


def _team_from_yaml(
    key: str, raw: Mapping[str, Any], env: Mapping[str, str]
) -> TeamConfig:
    linear_team_key = raw.get("linear_team_key")
    if not linear_team_key:
        raise ConfigError(f"team '{key}' is missing linear_team_key")

    secret_env = raw.get("hmac_secret_env")
    if not secret_env:
        raise ConfigError(f"team '{key}' is missing hmac_secret_env")

    return TeamConfig(
        key=key,
        linear_team_key=str(linear_team_key),
        hmac_secret=_require_env(env, secret_env, f"HMAC secret for team '{key}'"),
        open_state=raw.get("open_state"),
        close_state=raw.get("close_state"),
        reopen_state=raw.get("reopen_state"),
        labels=tuple(raw.get("labels") or ()),
        priority_from_severity=bool(raw.get("priority_from_severity", True)),
        severity_labels=bool(raw.get("severity_labels", True)),
        severity_label_prefix=str(
            raw.get("severity_label_prefix", DEFAULT_SEVERITY_LABEL_PREFIX)
        ),
    )


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> Config:
    """Load and validate config.yaml, resolving every secret from the environment."""
    env = os.environ if env is None else env

    try:
        raw = yaml.safe_load(Path(path).read_text()) or {}
    except OSError as exc:
        raise ConfigError(f"unable to read config file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    linear = raw.get("linear") or {}
    server = raw.get("server") or {}
    teams_raw = raw.get("teams") or {}

    if not teams_raw:
        raise ConfigError("configuration must define at least one team")

    teams = {
        key: _team_from_yaml(key, team_raw or {}, env)
        for key, team_raw in teams_raw.items()
    }

    return Config(
        linear_api_key=_require_env(
            env, linear.get("api_key_env"), "Linear API key"
        ),
        linear_api_url=linear.get("api_url") or DEFAULT_LINEAR_API_URL,
        inbound_bearer_token=_require_env(
            env, server.get("inbound_bearer_token_env"), "inbound bearer token"
        ),
        database_url=server.get("database_url") or DEFAULT_DATABASE_URL,
        max_findings_per_issue=int(
            server.get("max_findings_per_issue") or DEFAULT_MAX_FINDINGS
        ),
        teams=teams,
    )
