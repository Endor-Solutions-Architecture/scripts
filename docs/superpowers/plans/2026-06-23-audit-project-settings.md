# audit_project_settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `audit-project-settings` (bash) into this repo as `audit_project_settings/main.py`, replacing `endorctl api` CLI calls and `jq` processing with direct REST calls and native Python, producing identical JSON output.

**Architecture:** Single `main.py` with pure functions for type normalization, namespace hierarchy building, apply logic, and output assembly. HTTP is isolated to two fetch helpers (`fetch_project`, `fetch_all_paged`). Auth follows the `dependency_resolution_summary` pattern: `--token` → `ENDOR_TOKEN` env var → `endorctl auth --print-access-token`.

**Tech Stack:** Python 3.10+, `requests~=2.32`, `argparse` (stdlib), `pytest` (test runner, not in requirements.txt)

## Global Constraints

- Python 3.10+ (PEP 604 union types `X | Y` required)
- `requirements.txt` contains only `requests~=2.32` — no other runtime deps
- Output JSON must be schema-identical to the bash original (same keys, same nesting)
- Auth priority order: `--token` CLI flag → `ENDOR_TOKEN` env var → `endorctl auth --print-access-token`
- `argparse` positional args: `namespace`, `project_uuid`, optional `api_url`
- Default API URL: `https://api.endorlabs.com`; env var override: `ENDOR_API`
- All progress/error messages go to `stderr`; JSON output goes to `stdout`
- Run tests from the repo root: `pytest audit_project_settings/tests/ -v`

---

### Task 1: Scaffold — requirements, auth, project fetch

**Files:**
- Create: `audit_project_settings/requirements.txt`
- Create: `audit_project_settings/main.py` (partial: imports + `AuthError` + `resolve_token` + `fetch_project` + `DEFAULT_API_URL`)
- Create: `audit_project_settings/tests/__init__.py` (empty)
- Create: `audit_project_settings/tests/test_audit_project_settings.py`

**Interfaces:**
- Produces:
  - `AuthError(RuntimeError)` — raised when no token can be resolved
  - `resolve_token(explicit: str | None) -> str` — returns a bearer JWT
  - `fetch_project(api_url: str, namespace: str, uuid: str, token: str) -> dict` — returns the raw project API object; raises `RuntimeError` on HTTP error, `SystemExit(1)` if project not found
  - `DEFAULT_API_URL: str = "https://api.endorlabs.com"`

- [ ] **Step 1: Create `requirements.txt`**

```
requests~=2.32
```

- [ ] **Step 2: Write failing tests for `resolve_token` and `fetch_project`**

File: `audit_project_settings/tests/test_audit_project_settings.py`

```python
import os
from unittest.mock import MagicMock, patch

import pytest

from audit_project_settings.main import AuthError, fetch_project, resolve_token


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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/lmoreno/git/endor-internal/scripts
pytest audit_project_settings/tests/test_audit_project_settings.py -v
```

Expected: `ModuleNotFoundError: No module named 'audit_project_settings'`

- [ ] **Step 4: Create `audit_project_settings/main.py`**

```python
import argparse
import json
import os
import subprocess
import sys

import requests

DEFAULT_API_URL = "https://api.endorlabs.com"


class AuthError(RuntimeError):
    """Raised when no token can be resolved."""


def resolve_token(explicit: str | None) -> str:
    """Return a JWT. Priority: explicit → ENDOR_TOKEN → endorctl auth."""
    if explicit:
        return explicit
    env = os.environ.get("ENDOR_TOKEN")
    if env:
        return env
    try:
        result = subprocess.run(
            ["endorctl", "auth", "--print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise AuthError(
            "endorctl is not installed. Install it or pass --token / set ENDOR_TOKEN."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AuthError(
            "endorctl auth failed — run `endorctl auth login` first, "
            "or set ENDOR_TOKEN. stderr:\n" + (exc.stderr or "")
        ) from exc
    return result.stdout.strip()


def fetch_project(api_url: str, namespace: str, uuid: str, token: str) -> dict:
    """GET /v1/namespaces/{namespace}/projects/{uuid}. Exits 1 if not found."""
    url = f"{api_url.rstrip('/')}/v1/namespaces/{namespace}/projects/{uuid}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    if resp.status_code >= 400:
        print(f"ERROR: Could not fetch project {uuid} in namespace {namespace} "
              f"(HTTP {resp.status_code})", file=sys.stderr)
        sys.exit(1)
    return resp.json()
```

- [ ] **Step 5: Create empty `audit_project_settings/tests/__init__.py`**

Create an empty file at `audit_project_settings/tests/__init__.py`.

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 7: Commit**

```bash
git add audit_project_settings/
git commit -m "feat: scaffold audit_project_settings with auth and project fetch"
```

---

### Task 2: Policy type normalization + namespace hierarchy

**Files:**
- Modify: `audit_project_settings/main.py` (add `normalize_policy_types`, `build_ns_hierarchy`)
- Modify: `audit_project_settings/tests/test_audit_project_settings.py` (add tests)

**Interfaces:**
- Consumes: nothing from prior tasks
- Produces:
  - `POLICY_TYPE_ALIASES: dict[str, str]` — alias → full enum name mapping
  - `normalize_policy_types(raw: str) -> list[str]` — converts comma-separated aliases/full names to `POLICY_TYPE_*` list; warns on unknown aliases to stderr; returns `[]` for empty string
  - `build_ns_hierarchy(namespace: str) -> list[str]` — `"a.b.c"` → `["a", "a.b", "a.b.c"]`

- [ ] **Step 1: Write failing tests**

Append to `audit_project_settings/tests/test_audit_project_settings.py`:

```python
from audit_project_settings.main import build_ns_hierarchy, normalize_policy_types


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "normalize or hierarchy"
```

Expected: `ImportError` — functions not yet defined

- [ ] **Step 3: Add `POLICY_TYPE_ALIASES`, `normalize_policy_types`, and `build_ns_hierarchy` to `main.py`**

Append after `fetch_project`:

```python
POLICY_TYPE_ALIASES: dict[str, str] = {
    "EXCEPTION": "POLICY_TYPE_EXCEPTION",
    "ACTION": "POLICY_TYPE_ADMISSION",
    "FINDING": "POLICY_TYPE_USER_FINDING",
    "NOTIFICATION": "POLICY_TYPE_NOTIFICATION",
    "ADMISSION": "POLICY_TYPE_ADMISSION",
    "REMEDIATION": "POLICY_TYPE_REMEDIATION",
}


def normalize_policy_types(raw: str) -> list[str]:
    """Convert comma-separated aliases/full names to POLICY_TYPE_* list."""
    if not raw:
        return []
    result = []
    for token in raw.split(","):
        upper = token.strip().upper()
        if upper in POLICY_TYPE_ALIASES:
            result.append(POLICY_TYPE_ALIASES[upper])
        elif upper.startswith("POLICY_TYPE_"):
            result.append(upper)
        else:
            print(f"WARNING: unknown policy type '{token.strip()}' — skipped. "
                  "Valid aliases: exception, action, finding, notification, admission, remediation",
                  file=sys.stderr)
    return result


def build_ns_hierarchy(namespace: str) -> list[str]:
    """'a.b.c' → ['a', 'a.b', 'a.b.c']"""
    parts = namespace.split(".")
    levels = []
    for i in range(len(parts)):
        levels.append(".".join(parts[: i + 1]))
    return levels
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "normalize or hierarchy"
```

Expected: all 9 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add audit_project_settings/main.py audit_project_settings/tests/test_audit_project_settings.py
git commit -m "feat: add policy type normalization and namespace hierarchy builder"
```

---

### Task 3: Paginated fetch for policies and scan profiles

**Files:**
- Modify: `audit_project_settings/main.py` (add `fetch_all_paged`)
- Modify: `audit_project_settings/tests/test_audit_project_settings.py` (add tests)

**Interfaces:**
- Consumes: nothing from prior tasks
- Produces:
  - `fetch_all_paged(url: str, token: str, params: dict | None = None) -> list[dict]` — GETs the URL, pages through `list.response.next_page_token`, collects all `list.objects` entries; raises `RuntimeError` on HTTP ≥ 400

- [ ] **Step 1: Write failing tests**

Append to `audit_project_settings/tests/test_audit_project_settings.py`:

```python
from audit_project_settings.main import fetch_all_paged


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "paged"
```

Expected: `ImportError` — `fetch_all_paged` not yet defined

- [ ] **Step 3: Add `fetch_all_paged` to `main.py`**

Append after `build_ns_hierarchy`:

```python
def fetch_all_paged(url: str, token: str, params: dict | None = None) -> list[dict]:
    """GET url with pagination, collecting all list.objects entries."""
    headers = {"Authorization": f"Bearer {token}"}
    params = dict(params or {})
    params.setdefault("list_parameters.page_size", 25)
    objects: list[dict] = []
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
        body = resp.json()
        objects.extend(body.get("list", {}).get("objects") or [])
        next_token = (body.get("list", {}).get("response", {}) or {}).get("next_page_token")
        if not next_token:
            break
        params["list_parameters.page_token"] = next_token
    return objects
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "paged"
```

Expected: all 4 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add audit_project_settings/main.py audit_project_settings/tests/test_audit_project_settings.py
git commit -m "feat: add paginated fetch helper"
```

---

### Task 4: Apply logic + entry builders

**Files:**
- Modify: `audit_project_settings/main.py` (add `determine_applies`, `build_policy_entry`, `build_profile_entry`)
- Modify: `audit_project_settings/tests/test_audit_project_settings.py` (add tests)

**Interfaces:**
- Consumes: nothing from prior tasks
- Produces:
  - `determine_applies(policy: dict, project_uuid: str, project_tags: list[str]) -> dict` — returns `{"applies": bool, "reason": str}`
  - `build_policy_entry(policy: dict, applies: dict, app_base: str, query_ns: str) -> dict` — returns one policy entry matching the output schema
  - `build_profile_entry(profile: dict) -> dict` — returns one scan profile entry matching the output schema

- [ ] **Step 1: Write failing tests**

Append to `audit_project_settings/tests/test_audit_project_settings.py`:

```python
from audit_project_settings.main import (
    build_policy_entry,
    build_profile_entry,
    determine_applies,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "applies or policy_entry or profile_entry"
```

Expected: `ImportError` — functions not yet defined

- [ ] **Step 3: Add `determine_applies`, `build_policy_entry`, `build_profile_entry` to `main.py`**

Append after `fetch_all_paged`:

```python
def determine_applies(
    policy: dict, project_uuid: str, project_tags: list[str]
) -> dict:
    """Return {applies, reason} for a policy against a project."""
    spec = policy.get("spec", {}) or {}
    exceptions = spec.get("project_exceptions") or []
    selector = spec.get("project_selector") or []

    if project_uuid in exceptions:
        return {"applies": False, "reason": "excluded — listed in project_exceptions"}
    if not selector:
        return {"applies": True, "reason": "all projects in namespace"}

    matched = [t for t in selector if t in project_tags]
    if matched:
        return {"applies": True, "reason": "tag-scoped match on: " + ", ".join(matched)}
    return {"applies": False, "reason": f"tag-scoped no match (selector: {', '.join(selector)})"}


def build_policy_entry(
    policy: dict, applies: dict, app_base: str, query_ns: str
) -> dict:
    """Build a single policy output entry."""
    return {
        "uuid": policy.get("uuid", ""),
        "name": (policy.get("meta") or {}).get("name", ""),
        "policy_type": (policy.get("spec") or {}).get("policy_type", ""),
        "applies": applies["applies"],
        "reason": applies["reason"],
        "disabled": (policy.get("spec") or {}).get("disable", False),
        "url": f"{app_base}/t/{query_ns}/policies/{policy.get('uuid', '')}",
    }


def build_profile_entry(profile: dict) -> dict:
    """Build a single scan profile output entry."""
    return {
        "uuid": profile.get("uuid", ""),
        "name": (profile.get("meta") or {}).get("name", ""),
        "is_default": (profile.get("spec") or {}).get("is_default", False),
        "applies": True,
        "reason": "all projects in namespace (no project-level selector)",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "applies or policy_entry or profile_entry"
```

Expected: all 9 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add audit_project_settings/main.py audit_project_settings/tests/test_audit_project_settings.py
git commit -m "feat: add apply logic and entry builders"
```

---

### Task 5: Output assembly + main orchestration

**Files:**
- Modify: `audit_project_settings/main.py` (add `assemble_output`, `main()`, `if __name__ == "__main__"`)
- Modify: `audit_project_settings/tests/test_audit_project_settings.py` (add integration test)

**Interfaces:**
- Consumes:
  - `resolve_token(explicit: str | None) -> str`
  - `fetch_project(api_url, namespace, uuid, token) -> dict`
  - `fetch_all_paged(url, token, params) -> list[dict]`
  - `normalize_policy_types(raw) -> list[str]`
  - `build_ns_hierarchy(namespace) -> list[str]`
  - `determine_applies(policy, project_uuid, project_tags) -> dict`
  - `build_policy_entry(policy, applies, app_base, query_ns) -> dict`
  - `build_profile_entry(profile) -> dict`
- Produces: `main(argv: list[str] | None = None) -> int` — entry point

- [ ] **Step 1: Write a failing integration test**

Append to `audit_project_settings/tests/test_audit_project_settings.py`:

```python
from audit_project_settings.main import main


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v -k "main"
```

Expected: `ImportError` — `main` not yet defined

- [ ] **Step 3: Add `assemble_output` and `main()` to `main.py`**

Append after `build_profile_entry`:

```python
def _app_base(api_url: str) -> str:
    """'https://api.endorlabs.com' → 'https://app.endorlabs.com'"""
    return api_url.replace("//api.", "//app.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit policies and scan profiles that apply to an Endor Labs project."
    )
    parser.add_argument("namespace", help="Project's full namespace (e.g. org.repo.name)")
    parser.add_argument("project_uuid", help="Project UUID")
    parser.add_argument(
        "api_url",
        nargs="?",
        default=os.environ.get("ENDOR_API", DEFAULT_API_URL),
        help="API base URL (default: $ENDOR_API or https://api.endorlabs.com)",
    )
    parser.add_argument("--all", dest="show_all", action="store_true",
                        help="Include policies/profiles that do not apply to this project")
    parser.add_argument("--policy-types", default="",
                        help="Comma-separated policy type aliases or full enum names")
    parser.add_argument("--token", default=None,
                        help="Override bearer token (overrides ENDOR_TOKEN / endorctl)")
    args = parser.parse_args(argv)

    try:
        token = resolve_token(args.token)
    except AuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    project = fetch_project(args.api_url, args.namespace, args.project_uuid, token)
    project_name = (project.get("meta") or {}).get("name", "")
    project_tags = (project.get("meta") or {}).get("tags") or []

    normalized_types = normalize_policy_types(args.policy_types)
    ns_hierarchy = build_ns_hierarchy(args.namespace)
    app_base = _app_base(args.api_url)

    base_url = args.api_url.rstrip("/")
    policy_params: dict = {}
    if normalized_types:
        type_list = ", ".join(normalized_types)
        policy_params["list_parameters.filter"] = f"spec.policy_type in [{type_list}]"

    ns_entries = []
    for query_ns in ns_hierarchy:
        scope = "own" if query_ns == args.namespace else "parent"

        policies = fetch_all_paged(
            f"{base_url}/v1/namespaces/{query_ns}/policies",
            token,
            dict(policy_params),
        )
        profiles = fetch_all_paged(
            f"{base_url}/v1/namespaces/{query_ns}/scan-profiles",
            token,
        )

        policy_entries = [
            build_policy_entry(p, determine_applies(p, args.project_uuid, project_tags), app_base, query_ns)
            for p in policies
        ]
        profile_entries = [build_profile_entry(p) for p in profiles]

        ns_entries.append({
            "namespace": query_ns,
            "scope": scope,
            "policies": policy_entries,
            "scan_profiles": profile_entries,
        })

    output = {
        "meta": {
            "namespace": args.namespace,
            "project_uuid": args.project_uuid,
            "api": args.api_url,
            "show_all": args.show_all,
            "policy_types": normalized_types if normalized_types else "all",
        },
        "project": {
            "name": project_name,
            "uuid": args.project_uuid,
            "tags": project_tags,
        },
        "namespaces": ns_entries,
    }

    if not args.show_all:
        output["namespaces"] = [
            {
                **ns,
                "policies": [p for p in ns["policies"] if p["applies"]],
                "scan_profiles": [p for p in ns["scan_profiles"] if p["applies"]],
            }
            for ns in output["namespaces"]
        ]

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all tests**

```bash
pytest audit_project_settings/tests/test_audit_project_settings.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add audit_project_settings/main.py audit_project_settings/tests/test_audit_project_settings.py
git commit -m "feat: add output assembly and main orchestration"
```

---

### Task 6: README

**Files:**
- Create: `audit_project_settings/README.md`

**Interfaces:**
- Consumes: finalized CLI interface from Task 5
- Produces: `README.md` with prerequisites, usage, options, policy types table, output schema, examples

- [ ] **Step 1: Create `audit_project_settings/README.md`**

```markdown
# audit_project_settings

Audits all policies and scan profiles that are visible to an Endor Labs project, tracing each one through the namespace hierarchy to explain **why** it applies. Outputs structured JSON suitable for saving, diffing, or piping into `jq`.

Primary use case: **project migration** — run this before moving a project to a new namespace to get a complete inventory of every policy and scan profile that needs to be recreated or reattached in the destination.

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt`
- `endorctl` authenticated (or set `ENDOR_TOKEN`, or pass `--token`)
- `jq` on your `PATH` (optional — for filtering the JSON output)

## Usage

```
python main.py [options] <namespace> <project-uuid> [api-url]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `namespace` | Yes | The project's full namespace (e.g. `acme.backend.api`) |
| `project-uuid` | Yes | The project's UUID |
| `api-url` | No | API base URL. Defaults to `$ENDOR_API` if set, otherwise `https://api.endorlabs.com` |

### Options

| Option | Description |
|---|---|
| `--all` | Include policies and scan profiles that do **not** apply to this project. Default: only items that apply are shown. |
| `--policy-types <types>` | Comma-separated list of policy types to include. Default: all types. See [Policy Types](#policy-types) below. |
| `--token <token>` | Explicit bearer token. Overrides `ENDOR_TOKEN` env var and `endorctl auth`. |

## Policy Types

The `--policy-types` flag accepts short aliases or full API enum names:

| Alias | API enum | What it does |
|---|---|---|
| `exception` | `POLICY_TYPE_EXCEPTION` | Dismisses findings — exempts specific findings from action policies |
| `action` | `POLICY_TYPE_ADMISSION` | **Blocks CI/CD pipelines** — "Break the Build" (exit 128) or "Warn" (exit 0) |
| `finding` | `POLICY_TYPE_USER_FINDING` | Creates/raises findings — enables or defines custom finding rules |
| `notification` | `POLICY_TYPE_NOTIFICATION` | Sends alerts (Jira, Slack, etc.) when findings match criteria |
| `admission` | `POLICY_TYPE_ADMISSION` | Same as `action` (full alias for the API enum name) |
| `remediation` | `POLICY_TYPE_REMEDIATION` | Auto-remediates findings when a safe upgrade is available |

Full API enum names (e.g. `POLICY_TYPE_EXCEPTION`) are also accepted directly.

## How Namespace Inheritance Works

Endor Labs namespaces are dot-delimited hierarchies. A project in `acme.backend.api` is also subject to policies defined in `acme.backend` and `acme`. This script queries every level — root to own — and reports each policy's source namespace and scope.

Each policy's `reason` field explains exactly why it applies (or doesn't):

| Reason | Meaning |
|---|---|
| `all projects in namespace` | No `project_selector` set — applies to every project in that namespace |
| `tag-scoped match on: <tags>` | Policy has a `project_selector` and this project has a matching tag |
| `tag-scoped no match (selector: …)` | Policy has a `project_selector` but this project's tags don't overlap |
| `excluded — listed in project_exceptions` | This project's UUID is explicitly excluded from the policy |

## Output Schema

```
{
  "meta": {
    "namespace":     string,
    "project_uuid":  string,
    "api":           string,
    "show_all":      bool,
    "policy_types":  array | "all"
  },
  "project": {
    "name":  string,
    "uuid":  string,
    "tags":  array
  },
  "namespaces": [
    {
      "namespace":  string,
      "scope":      "own" | "parent",
      "policies": [
        {
          "uuid":         string,
          "name":         string,
          "policy_type":  string,
          "applies":      bool,
          "reason":       string,
          "disabled":     bool,
          "url":          string
        }
      ],
      "scan_profiles": [
        {
          "uuid":        string,
          "name":        string,
          "is_default":  bool,
          "applies":     bool,
          "reason":      string
        }
      ]
    }
  ]
}
```

Note: `ScanProfile` resources have no `project_selector` — all scan profiles in a namespace (and its parents) apply to every project in that namespace.

## Examples

### Basic audit — only items that apply

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Save to file for migration reference

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 > audit.json
```

### Exception and action policies only

```bash
python main.py --policy-types exception,action \
  acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Include non-matching policies (full namespace inventory)

```bash
python main.py --all --policy-types exception,action \
  acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2
```

### Run against staging

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  https://api.staging.endorlabs.com
```

### Extract just the policy names and URLs that apply

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  | jq '.namespaces[] | {ns: .namespace, scope: .scope, policies: [.policies[] | {name, url, policy_type}]}'
```

### Count applying policies per namespace level

```bash
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 \
  | jq '.namespaces[] | {namespace, policy_count: (.policies | length), profile_count: (.scan_profiles | length)}'
```
```

- [ ] **Step 2: Commit**

```bash
git add audit_project_settings/README.md
git commit -m "docs: add README for audit_project_settings"
```
