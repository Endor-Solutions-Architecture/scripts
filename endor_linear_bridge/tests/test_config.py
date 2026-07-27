import textwrap

import pytest

from endor_linear_bridge.config import ConfigError, load_config


def write_config(tmp_path, body):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(body))
    return path


MINIMAL = """
    linear:
      api_key_env: LINEAR_API_KEY
    server:
      inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
    teams:
      plat:
        linear_team_key: PLAT
        hmac_secret_env: ENDOR_HMAC_PLAT
"""

ENV = {
    "LINEAR_API_KEY": "lin_api_key",
    "BRIDGE_BEARER_TOKEN": "inbound-token",
    "ENDOR_HMAC_PLAT": "hmac-secret",
}


def test_load_config_resolves_secrets_from_env(tmp_path):
    cfg = load_config(write_config(tmp_path, MINIMAL), env=ENV)

    assert cfg.linear_api_key == "lin_api_key"
    assert cfg.inbound_bearer_token == "inbound-token"
    assert cfg.teams["plat"].hmac_secret == "hmac-secret"


def test_load_config_applies_defaults(tmp_path):
    cfg = load_config(write_config(tmp_path, MINIMAL), env=ENV)
    team = cfg.teams["plat"]

    assert cfg.linear_api_url == "https://api.linear.app/graphql"
    assert cfg.database_url == "sqlite:///./bridge.db"
    assert cfg.max_findings_per_issue == 50
    assert team.key == "plat"
    assert team.linear_team_key == "PLAT"
    assert team.open_state is None
    assert team.close_state is None
    assert team.reopen_state is None
    assert team.labels == ()
    assert team.priority_from_severity is True
    assert team.severity_labels is True
    assert team.severity_label_prefix == "endor-"


def test_load_config_reads_overrides(tmp_path):
    path = write_config(tmp_path, """
        linear:
          api_key_env: LINEAR_API_KEY
          api_url: http://localhost:9999/graphql
        server:
          inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
          database_url: sqlite:///./other.db
          max_findings_per_issue: 10
        teams:
          plat:
            linear_team_key: PLAT
            hmac_secret_env: ENDOR_HMAC_PLAT
            open_state: Triage
            close_state: Done
            reopen_state: Todo
            labels: [endorlabs, security]
            priority_from_severity: false
            severity_labels: false
            severity_label_prefix: "sev-"
    """)

    cfg = load_config(path, env=ENV)
    team = cfg.teams["plat"]

    assert cfg.linear_api_url == "http://localhost:9999/graphql"
    assert cfg.database_url == "sqlite:///./other.db"
    assert cfg.max_findings_per_issue == 10
    assert team.open_state == "Triage"
    assert team.close_state == "Done"
    assert team.reopen_state == "Todo"
    assert team.labels == ("endorlabs", "security")
    assert team.priority_from_severity is False
    assert team.severity_labels is False
    assert team.severity_label_prefix == "sev-"


def test_load_config_rejects_missing_env_var(tmp_path):
    env = dict(ENV)
    del env["ENDOR_HMAC_PLAT"]

    with pytest.raises(ConfigError, match="ENDOR_HMAC_PLAT"):
        load_config(write_config(tmp_path, MINIMAL), env=env)


def test_load_config_rejects_empty_env_var(tmp_path):
    env = dict(ENV, ENDOR_HMAC_PLAT="")

    with pytest.raises(ConfigError, match="ENDOR_HMAC_PLAT"):
        load_config(write_config(tmp_path, MINIMAL), env=env)


def test_load_config_rejects_missing_teams(tmp_path):
    path = write_config(tmp_path, """
        linear:
          api_key_env: LINEAR_API_KEY
        server:
          inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
        teams: {}
    """)

    with pytest.raises(ConfigError, match="at least one team"):
        load_config(path, env=ENV)


def test_load_config_rejects_team_without_linear_team_key(tmp_path):
    path = write_config(tmp_path, """
        linear:
          api_key_env: LINEAR_API_KEY
        server:
          inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
        teams:
          plat:
            hmac_secret_env: ENDOR_HMAC_PLAT
    """)

    with pytest.raises(ConfigError, match="linear_team_key"):
        load_config(path, env=ENV)


def test_load_config_rejects_team_without_hmac_secret_env(tmp_path):
    path = write_config(tmp_path, """
        linear:
          api_key_env: LINEAR_API_KEY
        server:
          inbound_bearer_token_env: BRIDGE_BEARER_TOKEN
        teams:
          plat:
            linear_team_key: PLAT
    """)

    with pytest.raises(ConfigError, match="hmac_secret_env"):
        load_config(path, env=ENV)
