import os
from unittest.mock import MagicMock, patch

import pytest

import json

from audit_project_settings.main import (
    AuthError,
    build_ns_hierarchy,
    build_policy_entry,
    build_profile_entry,
    determine_applies,
    fetch_all_paged,
    fetch_project,
    main,
    normalize_policy_types,
    resolve_token,
)


# --- resolve_token ---

def test_resolve_token_returns_explicit_token():
    assert resolve_token("mytoken") == "mytoken"


def test_resolve_token_reads_env_var(monkeypatch):
    monkeypatch.setenv("ENDOR_TOKEN", "envtoken")
    assert resolve_token(None) == "envtoken"


def test_resolve_token_calls_endorctl_when_no_env(monkeypatch):
    monkeypatch.delenv("ENDOR_TOKEN", raising=False)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ctltoken\n")
        assert resolve_token(None) == "ctltoken"
        mock_run.assert_called_once()


def test_resolve_token_raises_auth_error_when_endorctl_missing(monkeypatch):
    monkeypatch.delenv("ENDOR_TOKEN", raising=False)
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(AuthError, match="endorctl is not installed"):
            resolve_token(None)


def test_resolve_token_raises_auth_error_when_endorctl_fails(monkeypatch):
    import subprocess
    monkeypatch.delenv("ENDOR_TOKEN", raising=False)
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "endorctl", stderr="auth failed")):
        with pytest.raises(AuthError, match="endorctl auth failed"):
            resolve_token(None)


# --- fetch_project ---

def test_fetch_project_returns_project_object():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"uuid": "abc123", "meta": {"name": "my-repo", "tags": ["prod"]}}
    with patch("requests.get", return_value=mock_resp):
        result = fetch_project("https://api.endorlabs.com", "myns", "abc123", "tok")
    assert result["uuid"] == "abc123"


def test_fetch_project_exits_on_http_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "not found"
    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            fetch_project("https://api.endorlabs.com", "myns", "missing", "tok")


# --- normalize_policy_types ---


def test_normalize_empty_string_returns_empty_list():
    assert normalize_policy_types("") == []


def test_normalize_short_aliases():
    result = normalize_policy_types("exception,action,finding")
    assert result == [
        "POLICY_TYPE_EXCEPTION",
        "POLICY_TYPE_ADMISSION",
        "POLICY_TYPE_USER_FINDING",
    ]


def test_normalize_full_enum_names_pass_through():
    result = normalize_policy_types("POLICY_TYPE_EXCEPTION,POLICY_TYPE_REMEDIATION")
    assert result == ["POLICY_TYPE_EXCEPTION", "POLICY_TYPE_REMEDIATION"]


def test_normalize_mixed_aliases_and_full_names():
    result = normalize_policy_types("notification,POLICY_TYPE_REMEDIATION")
    assert result == ["POLICY_TYPE_NOTIFICATION", "POLICY_TYPE_REMEDIATION"]


def test_normalize_unknown_alias_warns_and_skips(capsys):
    result = normalize_policy_types("bogus")
    assert result == []
    captured = capsys.readouterr()
    assert "bogus" in captured.err


def test_normalize_action_and_admission_both_map_to_admission():
    assert normalize_policy_types("action") == ["POLICY_TYPE_ADMISSION"]
    assert normalize_policy_types("admission") == ["POLICY_TYPE_ADMISSION"]


# --- build_ns_hierarchy ---


def test_build_ns_hierarchy_single_part():
    assert build_ns_hierarchy("root") == ["root"]


def test_build_ns_hierarchy_three_parts():
    assert build_ns_hierarchy("a.b.c") == ["a", "a.b", "a.b.c"]


def test_build_ns_hierarchy_two_parts():
    assert build_ns_hierarchy("org.project") == ["org", "org.project"]


# --- fetch_all_paged ---

def _make_page(objects, next_token=None):
    resp = {"list": {"objects": objects}}
    if next_token:
        resp["list"]["response"] = {"next_page_token": next_token}
    else:
        resp["list"]["response"] = {"next_page_token": ""}
    return resp


def test_fetch_all_paged_single_page():
    page = _make_page([{"uuid": "p1"}, {"uuid": "p2"}])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = page
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = fetch_all_paged("https://api.endorlabs.com/v1/namespaces/ns/policies", "tok")
    assert result == [{"uuid": "p1"}, {"uuid": "p2"}]
    assert mock_get.call_count == 1


def test_fetch_all_paged_multiple_pages():
    page1 = _make_page([{"uuid": "p1"}], next_token="tok2")
    page2 = _make_page([{"uuid": "p2"}])
    mock_resp1 = MagicMock(status_code=200)
    mock_resp1.json.return_value = page1
    mock_resp2 = MagicMock(status_code=200)
    mock_resp2.json.return_value = page2
    with patch("requests.get", side_effect=[mock_resp1, mock_resp2]) as mock_get:
        result = fetch_all_paged("https://api.endorlabs.com/v1/namespaces/ns/policies", "tok")
    assert result == [{"uuid": "p1"}, {"uuid": "p2"}]
    assert mock_get.call_count == 2
    # second call must carry the page token
    _, kwargs2 = mock_get.call_args_list[1]
    assert kwargs2["params"]["list_parameters.page_token"] == "tok2"


def test_fetch_all_paged_empty_objects():
    page = {"list": {"response": {"next_page_token": ""}}}
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = page
    with patch("requests.get", return_value=mock_resp):
        result = fetch_all_paged("https://api.endorlabs.com/v1/namespaces/ns/policies", "tok")
    assert result == []


def test_fetch_all_paged_raises_on_http_error():
    mock_resp = MagicMock(status_code=500, text="server error")
    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            fetch_all_paged("https://api.endorlabs.com/v1/namespaces/ns/policies", "tok")


# --- determine_applies ---

def _policy(selector=None, exceptions=None):
    return {
        "spec": {
            "project_selector": selector or [],
            "project_exceptions": exceptions or [],
        }
    }


def test_determine_applies_no_selector_applies_to_all():
    result = determine_applies(_policy(), "uuid1", ["prod"])
    assert result == {"applies": True, "reason": "all projects in namespace"}


def test_determine_applies_excluded_by_exception():
    result = determine_applies(_policy(exceptions=["uuid1"]), "uuid1", ["prod"])
    assert result["applies"] is False
    assert "project_exceptions" in result["reason"]


def test_determine_applies_tag_match():
    result = determine_applies(_policy(selector=["prod", "java"]), "uuid1", ["prod"])
    assert result["applies"] is True
    assert "prod" in result["reason"]


def test_determine_applies_tag_no_match():
    result = determine_applies(_policy(selector=["staging"]), "uuid1", ["prod"])
    assert result["applies"] is False
    assert "staging" in result["reason"]


def test_determine_applies_exception_takes_priority_over_selector():
    result = determine_applies(
        _policy(selector=["prod"], exceptions=["uuid1"]), "uuid1", ["prod"]
    )
    assert result["applies"] is False
    assert "project_exceptions" in result["reason"]


# --- build_policy_entry ---

def test_build_policy_entry_shape():
    policy = {
        "uuid": "pol1",
        "meta": {"name": "My Policy"},
        "spec": {
            "policy_type": "POLICY_TYPE_EXCEPTION",
            "disable": False,
            "project_selector": [],
            "project_exceptions": [],
        },
    }
    applies = {"applies": True, "reason": "all projects in namespace"}
    entry = build_policy_entry(policy, applies, "https://app.endorlabs.com", "myns")
    assert entry["uuid"] == "pol1"
    assert entry["name"] == "My Policy"
    assert entry["policy_type"] == "POLICY_TYPE_EXCEPTION"
    assert entry["applies"] is True
    assert entry["disabled"] is False
    assert entry["url"] == "https://app.endorlabs.com/t/myns/policies/pol1"


# --- build_profile_entry ---

def test_build_profile_entry_shape():
    profile = {
        "uuid": "prof1",
        "meta": {"name": "Default Profile"},
        "spec": {"is_default": True},
    }
    entry = build_profile_entry(profile)
    assert entry["uuid"] == "prof1"
    assert entry["name"] == "Default Profile"
    assert entry["is_default"] is True
    assert entry["applies"] is True
    assert "reason" in entry


# --- integration: main() ---

def test_main_outputs_json_to_stdout(capsys, monkeypatch):
    monkeypatch.setenv("ENDOR_TOKEN", "testtoken")

    project_resp = MagicMock(status_code=200)
    project_resp.json.return_value = {
        "uuid": "proj1",
        "meta": {"name": "github.com/org/repo", "tags": ["prod"]},
    }

    policies_resp = MagicMock(status_code=200)
    policies_resp.json.return_value = {
        "list": {
            "objects": [{
                "uuid": "pol1",
                "meta": {"name": "Exc Policy"},
                "spec": {
                    "policy_type": "POLICY_TYPE_EXCEPTION",
                    "disable": False,
                    "project_selector": [],
                    "project_exceptions": [],
                },
            }],
            "response": {"next_page_token": ""},
        }
    }

    profiles_resp = MagicMock(status_code=200)
    profiles_resp.json.return_value = {
        "list": {
            "objects": [],
            "response": {"next_page_token": ""},
        }
    }

    with patch("requests.get", side_effect=[
        project_resp,    # fetch_project for "myns"
        policies_resp,   # policies for "myns"
        profiles_resp,   # scan_profiles for "myns"
    ]):
        rc = main(["myns", "proj1"])

    assert rc == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["project"]["uuid"] == "proj1"
    assert output["meta"]["namespace"] == "myns"
    assert len(output["namespaces"]) == 1
    assert output["namespaces"][0]["scope"] == "own"
    assert output["namespaces"][0]["policies"][0]["uuid"] == "pol1"


def test_main_exits_1_on_missing_args(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_main_filters_applies_by_default(capsys, monkeypatch):
    monkeypatch.setenv("ENDOR_TOKEN", "testtoken")

    project_resp = MagicMock(status_code=200)
    project_resp.json.return_value = {
        "uuid": "proj1",
        "meta": {"name": "repo", "tags": []},
    }

    policies_resp = MagicMock(status_code=200)
    policies_resp.json.return_value = {
        "list": {
            "objects": [
                {
                    "uuid": "pol_applies",
                    "meta": {"name": "Applies"},
                    "spec": {"policy_type": "POLICY_TYPE_EXCEPTION", "disable": False,
                             "project_selector": [], "project_exceptions": []},
                },
                {
                    "uuid": "pol_excluded",
                    "meta": {"name": "Excluded"},
                    "spec": {"policy_type": "POLICY_TYPE_EXCEPTION", "disable": False,
                             "project_selector": [], "project_exceptions": ["proj1"]},
                },
            ],
            "response": {"next_page_token": ""},
        }
    }

    profiles_resp = MagicMock(status_code=200)
    profiles_resp.json.return_value = {
        "list": {"objects": [], "response": {"next_page_token": ""}}
    }

    with patch("requests.get", side_effect=[project_resp, policies_resp, profiles_resp]):
        rc = main(["myns", "proj1"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    policy_uuids = [p["uuid"] for p in out["namespaces"][0]["policies"]]
    assert "pol_applies" in policy_uuids
    assert "pol_excluded" not in policy_uuids


def _make_response(status_code, body):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body
    return mock_resp


def test_main_sends_policy_type_filter(monkeypatch):
    """Filter string sent to /policies must use the correct API format."""
    project_resp = {
        "meta": {"name": "my-project", "tags": []},
        "uuid": "proj-uuid",
    }

    captured_params = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        if "/projects/" in url:
            return _make_response(200, project_resp)
        if "/policies" in url:
            captured_params.update(params or {})
            return _make_response(200, {"list": {"objects": [], "response": {}}})
        return _make_response(200, {"list": {"objects": [], "response": {}}})

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setenv("ENDOR_TOKEN", "tok")

    main(["acme.backend", "proj-uuid", "--policy-types", "exception,action"])

    assert captured_params.get("list_parameters.filter") == (
        "spec.policy_type in [POLICY_TYPE_EXCEPTION, POLICY_TYPE_ADMISSION]"
    )
