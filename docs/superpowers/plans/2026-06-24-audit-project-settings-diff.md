# audit_project_settings diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `diff.py` to `audit_project_settings/` to compare two audit JSON outputs and show what policies and scan profiles are in A but missing from B, writing both a JSON result and a text summary to `generated_reports/`.

**Architecture:** Standalone `diff.py` with pure functions for data loading, name collection, missing-item detection, result assembly, and text formatting. `main()` orchestrates them and handles file I/O. Timestamp is generated in `main()` and passed into `write_outputs()` so file-writing is fully testable. Tests live in the existing `audit_project_settings/tests/` directory as a new file.

**Tech Stack:** Python 3.10+, stdlib only (`json`, `argparse`, `pathlib`, `datetime`, `sys`)

## Global Constraints

- Python 3.10+ (PEP 604 union types `X | Y` required)
- No new runtime dependencies — `diff.py` uses stdlib only; `requirements.txt` is not modified
- Matching is by policy/profile **name only**, case-sensitive, across all namespace levels
- Deduplication: if the same name appears in multiple namespace levels in A, report it only once
- Both output files are always written; text is also printed to stdout
- Output files: `generated_reports/diff_audit.<YYYYMMDD_HHMMSS>.json` and `.txt`
- `generated_reports/` is created if it does not exist
- Errors (missing file, bad JSON, missing keys) go to stderr; exit 1
- Run tests from repo root: `pytest audit_project_settings/tests/ -v`

---

### Task 1: Data loading + name extraction + missing-item finders

**Files:**
- Create: `audit_project_settings/diff.py` (partial — imports + `load_audit` + `collect_names` + `find_missing_policies` + `find_missing_profiles`)
- Create: `audit_project_settings/tests/test_diff.py`

**Interfaces:**
- Produces:
  - `load_audit(path: str) -> dict` — loads and validates JSON; exits 1 on missing file, bad JSON, or missing top-level keys `meta`/`project`/`namespaces`
  - `collect_names(audit: dict, resource: str) -> set[str]` — flattens all non-empty names for `resource` (`"policies"` or `"scan_profiles"`) across all namespace levels
  - `find_missing_policies(audit_a: dict, names_b: set[str]) -> list[dict]` — returns policies from A not in `names_b`, deduplicated by name; each entry: `{name, policy_type, source_namespace, disabled, url}`
  - `find_missing_profiles(audit_a: dict, names_b: set[str]) -> list[dict]` — returns scan profiles from A not in `names_b`, deduplicated; each entry: `{name, source_namespace, is_default}`

- [ ] **Step 1: Write failing tests**

File: `audit_project_settings/tests/test_diff.py`

```python
import json
import pytest
from audit_project_settings.diff import (
    collect_names,
    find_missing_policies,
    find_missing_profiles,
    load_audit,
)


# --- load_audit ---

def test_load_audit_returns_dict(tmp_path):
    f = tmp_path / "audit.json"
    f.write_text(json.dumps({"meta": {}, "project": {}, "namespaces": []}))
    result = load_audit(str(f))
    assert isinstance(result, dict)
    assert "namespaces" in result


def test_load_audit_exits_on_missing_file():
    with pytest.raises(SystemExit):
        load_audit("/nonexistent/path/audit.json")


def test_load_audit_exits_on_invalid_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    with pytest.raises(SystemExit):
        load_audit(str(f))


def test_load_audit_exits_on_missing_required_key(tmp_path):
    f = tmp_path / "audit.json"
    f.write_text(json.dumps({"meta": {}, "project": {}}))  # missing "namespaces"
    with pytest.raises(SystemExit):
        load_audit(str(f))


# --- collect_names ---

def test_collect_names_policies_across_namespaces():
    audit = {
        "namespaces": [
            {"policies": [{"name": "Pol A"}, {"name": "Pol B"}], "scan_profiles": []},
            {"policies": [{"name": "Pol C"}], "scan_profiles": []},
        ]
    }
    assert collect_names(audit, "policies") == {"Pol A", "Pol B", "Pol C"}


def test_collect_names_scan_profiles():
    audit = {
        "namespaces": [
            {"policies": [], "scan_profiles": [{"name": "Prof A"}, {"name": "Prof B"}]},
        ]
    }
    assert collect_names(audit, "scan_profiles") == {"Prof A", "Prof B"}


def test_collect_names_skips_empty_name():
    audit = {
        "namespaces": [
            {"policies": [{"name": ""}, {"name": "Pol A"}], "scan_profiles": []},
        ]
    }
    assert collect_names(audit, "policies") == {"Pol A"}


def test_collect_names_empty_namespaces():
    assert collect_names({"namespaces": []}, "policies") == set()


# --- find_missing_policies ---

def test_find_missing_policies_returns_items_not_in_b():
    audit_a = {"namespaces": [{"namespace": "ns1", "policies": [
        {"name": "Pol A", "policy_type": "POLICY_TYPE_EXCEPTION", "disabled": False, "url": "http://x"},
        {"name": "Pol B", "policy_type": "POLICY_TYPE_ADMISSION", "disabled": False, "url": "http://y"},
    ], "scan_profiles": []}]}
    result = find_missing_policies(audit_a, {"Pol B"})
    assert len(result) == 1
    assert result[0]["name"] == "Pol A"
    assert result[0]["source_namespace"] == "ns1"
    assert result[0]["policy_type"] == "POLICY_TYPE_EXCEPTION"
    assert result[0]["disabled"] is False


def test_find_missing_policies_deduplicates_same_name_across_ns():
    audit_a = {"namespaces": [
        {"namespace": "ns1", "policies": [
            {"name": "Pol A", "policy_type": "POLICY_TYPE_EXCEPTION", "disabled": False, "url": ""}
        ], "scan_profiles": []},
        {"namespace": "ns2", "policies": [
            {"name": "Pol A", "policy_type": "POLICY_TYPE_EXCEPTION", "disabled": False, "url": ""}
        ], "scan_profiles": []},
    ]}
    result = find_missing_policies(audit_a, set())
    assert len(result) == 1


def test_find_missing_policies_returns_empty_when_all_present():
    audit_a = {"namespaces": [{"namespace": "ns1", "policies": [
        {"name": "Pol A", "policy_type": "POLICY_TYPE_EXCEPTION", "disabled": False, "url": ""}
    ], "scan_profiles": []}]}
    assert find_missing_policies(audit_a, {"Pol A"}) == []


# --- find_missing_profiles ---

def test_find_missing_profiles_returns_items_not_in_b():
    audit_a = {"namespaces": [{"namespace": "ns1", "policies": [], "scan_profiles": [
        {"name": "Strict", "is_default": True},
        {"name": "Default", "is_default": False},
    ]}]}
    result = find_missing_profiles(audit_a, {"Default"})
    assert len(result) == 1
    assert result[0]["name"] == "Strict"
    assert result[0]["source_namespace"] == "ns1"
    assert result[0]["is_default"] is True


def test_find_missing_profiles_deduplicates_same_name_across_ns():
    audit_a = {"namespaces": [
        {"namespace": "ns1", "policies": [], "scan_profiles": [{"name": "Prof A", "is_default": False}]},
        {"namespace": "ns2", "policies": [], "scan_profiles": [{"name": "Prof A", "is_default": False}]},
    ]}
    result = find_missing_profiles(audit_a, set())
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/lmoreno/git/endor-internal/scripts
pytest audit_project_settings/tests/test_diff.py -v
```

Expected: `ModuleNotFoundError: No module named 'audit_project_settings.diff'`

- [ ] **Step 3: Create `audit_project_settings/diff.py`**

```python
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_audit(path: str) -> dict:
    """Load and validate a JSON audit file produced by main.py."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    for key in ("meta", "project", "namespaces"):
        if key not in data:
            print(
                f"ERROR: {path} is missing required key '{key}' — is it a valid audit output?",
                file=sys.stderr,
            )
            sys.exit(1)
    return data


def collect_names(audit: dict, resource: str) -> set[str]:
    """Flatten all non-empty names for resource across all namespace levels."""
    names: set[str] = set()
    for ns in audit.get("namespaces", []):
        for item in ns.get(resource, []):
            name = item.get("name", "")
            if name:
                names.add(name)
    return names


def find_missing_policies(audit_a: dict, names_b: set[str]) -> list[dict]:
    """Return policies from A whose names are absent from names_b, deduplicated."""
    missing: list[dict] = []
    seen: set[str] = set()
    for ns in audit_a.get("namespaces", []):
        for policy in ns.get("policies", []):
            name = policy.get("name", "")
            if name and name not in names_b and name not in seen:
                seen.add(name)
                missing.append({
                    "name": name,
                    "policy_type": policy.get("policy_type", ""),
                    "source_namespace": ns.get("namespace", ""),
                    "disabled": policy.get("disabled", False),
                    "url": policy.get("url", ""),
                })
    return missing


def find_missing_profiles(audit_a: dict, names_b: set[str]) -> list[dict]:
    """Return scan profiles from A whose names are absent from names_b, deduplicated."""
    missing: list[dict] = []
    seen: set[str] = set()
    for ns in audit_a.get("namespaces", []):
        for profile in ns.get("scan_profiles", []):
            name = profile.get("name", "")
            if name and name not in names_b and name not in seen:
                seen.add(name)
                missing.append({
                    "name": name,
                    "source_namespace": ns.get("namespace", ""),
                    "is_default": profile.get("is_default", False),
                })
    return missing
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_diff.py -v
```

Expected: all 14 tests PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
pytest audit_project_settings/tests/ -v
```

Expected: all 44 tests PASS (30 existing + 14 new)

- [ ] **Step 6: Commit**

```bash
git add audit_project_settings/diff.py audit_project_settings/tests/test_diff.py
git commit -m "feat: add diff.py data loading, name collection, and missing-item finders"
```

---

### Task 2: Result assembly + text formatter

**Files:**
- Modify: `audit_project_settings/diff.py` (append `build_result` + `format_text`)
- Modify: `audit_project_settings/tests/test_diff.py` (append tests)

**Interfaces:**
- Consumes:
  - `find_missing_policies(...)  -> list[dict]` where each dict has `{name, policy_type, source_namespace, disabled, url}`
  - `find_missing_profiles(...) -> list[dict]` where each dict has `{name, source_namespace, is_default}`
- Produces:
  - `build_result(audit_a: dict, audit_b: dict, missing_policies: list[dict], missing_profiles: list[dict]) -> dict` — assembles the final diff result matching the JSON output schema
  - `format_text(result: dict) -> str` — renders the human-readable text summary (no "Output:" footer — that's added by `main()`)

- [ ] **Step 1: Write failing tests**

Append to `audit_project_settings/tests/test_diff.py`:

```python
from audit_project_settings.diff import build_result, format_text


def _make_audit(namespace, project_name, project_uuid):
    return {
        "meta": {"namespace": namespace},
        "project": {"name": project_name, "uuid": project_uuid},
        "namespaces": [],
    }


# --- build_result ---

def test_build_result_meta_shape():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    result = build_result(a, b, [], [])
    assert result["meta"]["source_a"] == {"namespace": "ns.a", "project_name": "repo-a", "project_uuid": "uuid-a"}
    assert result["meta"]["source_b"] == {"namespace": "ns.b", "project_name": "repo-b", "project_uuid": "uuid-b"}


def test_build_result_summary_counts():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    policies = [{"name": "P1", "policy_type": "T", "source_namespace": "ns", "disabled": False, "url": ""}]
    profiles = [{"name": "Prof1", "source_namespace": "ns", "is_default": False}]
    result = build_result(a, b, policies, profiles)
    assert result["summary"]["missing_policy_count"] == 1
    assert result["summary"]["missing_scan_profile_count"] == 1


def test_build_result_passes_through_missing_lists():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    policies = [{"name": "P1", "policy_type": "POLICY_TYPE_EXCEPTION", "source_namespace": "ns", "disabled": True, "url": "http://x"}]
    result = build_result(a, b, policies, [])
    assert result["missing_policies"] == policies
    assert result["missing_scan_profiles"] == []


# --- format_text ---

def test_format_text_no_missing():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    result = build_result(a, b, [], [])
    text = format_text(result)
    assert "Diff: ns.a (uuid-a) → ns.b (uuid-b)" in text
    assert "Policies missing from B (0): none" in text
    assert "Scan profiles missing from B (0): none" in text
    assert "0 missing policies" in text
    assert "0 missing scan profiles" in text


def test_format_text_singular_policy():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    policies = [{"name": "Exc Policy", "policy_type": "POLICY_TYPE_EXCEPTION",
                 "source_namespace": "ns.a", "disabled": False, "url": "https://app/pol1"}]
    result = build_result(a, b, policies, [])
    text = format_text(result)
    assert "Policies missing from B (1):" in text
    assert "POLICY_TYPE_EXCEPTION (1):" in text
    assert "- Exc Policy  [ns.a] https://app/pol1" in text
    assert "1 missing policy," in text  # singular


def test_format_text_groups_policies_by_type():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    policies = [
        {"name": "P1", "policy_type": "POLICY_TYPE_EXCEPTION", "source_namespace": "ns", "disabled": False, "url": ""},
        {"name": "P2", "policy_type": "POLICY_TYPE_ADMISSION", "source_namespace": "ns", "disabled": False, "url": ""},
        {"name": "P3", "policy_type": "POLICY_TYPE_EXCEPTION", "source_namespace": "ns", "disabled": False, "url": ""},
    ]
    result = build_result(a, b, policies, [])
    text = format_text(result)
    assert "POLICY_TYPE_EXCEPTION (2):" in text
    assert "POLICY_TYPE_ADMISSION (1):" in text


def test_format_text_missing_scan_profile():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    profiles = [{"name": "Strict Profile", "source_namespace": "ns.a", "is_default": True}]
    result = build_result(a, b, [], profiles)
    text = format_text(result)
    assert "Scan profiles missing from B (1):" in text
    assert "- Strict Profile  [ns.a]" in text
    assert "1 missing scan profile" in text  # singular


def test_format_text_no_url_when_empty():
    a = _make_audit("ns.a", "repo-a", "uuid-a")
    b = _make_audit("ns.b", "repo-b", "uuid-b")
    policies = [{"name": "P1", "policy_type": "POLICY_TYPE_EXCEPTION",
                 "source_namespace": "ns", "disabled": False, "url": ""}]
    result = build_result(a, b, policies, [])
    text = format_text(result)
    assert "- P1  [ns]\n" in text  # no trailing URL
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_diff.py -v -k "build_result or format_text"
```

Expected: `ImportError` — functions not yet defined

- [ ] **Step 3: Append `build_result` and `format_text` to `diff.py`**

```python
def build_result(
    audit_a: dict,
    audit_b: dict,
    missing_policies: list[dict],
    missing_profiles: list[dict],
) -> dict:
    """Assemble the full diff result matching the JSON output schema."""
    def _meta(audit: dict) -> dict:
        return {
            "namespace": audit["meta"]["namespace"],
            "project_name": audit["project"]["name"],
            "project_uuid": audit["project"]["uuid"],
        }
    return {
        "meta": {
            "source_a": _meta(audit_a),
            "source_b": _meta(audit_b),
        },
        "missing_policies": missing_policies,
        "missing_scan_profiles": missing_profiles,
        "summary": {
            "missing_policy_count": len(missing_policies),
            "missing_scan_profile_count": len(missing_profiles),
        },
    }


def format_text(result: dict) -> str:
    """Render the human-readable text summary (no Output: footer)."""
    a = result["meta"]["source_a"]
    b = result["meta"]["source_b"]
    lines = [
        f"Diff: {a['namespace']} ({a['project_uuid']}) → {b['namespace']} ({b['project_uuid']})",
        "",
    ]

    missing_policies = result["missing_policies"]
    policy_count = len(missing_policies)
    if policy_count == 0:
        lines.append("Policies missing from B (0): none")
    else:
        lines.append(f"Policies missing from B ({policy_count}):")
        by_type: dict[str, list[dict]] = {}
        for p in missing_policies:
            by_type.setdefault(p["policy_type"], []).append(p)
        for ptype in sorted(by_type):
            entries = by_type[ptype]
            lines.append(f"  {ptype} ({len(entries)}):")
            for p in entries:
                line = f"    - {p['name']}  [{p['source_namespace']}]"
                if p.get("url"):
                    line += f" {p['url']}"
                lines.append(line)

    lines.append("")

    missing_profiles = result["missing_scan_profiles"]
    profile_count = len(missing_profiles)
    if profile_count == 0:
        lines.append("Scan profiles missing from B (0): none")
    else:
        lines.append(f"Scan profiles missing from B ({profile_count}):")
        for p in missing_profiles:
            lines.append(f"  - {p['name']}  [{p['source_namespace']}]")

    lines.append("")
    p_word = "policy" if policy_count == 1 else "policies"
    s_word = "scan profile" if profile_count == 1 else "scan profiles"
    lines.append(f"Summary: {policy_count} missing {p_word}, {profile_count} missing {s_word}.")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest audit_project_settings/tests/test_diff.py -v
```

Expected: all 22 tests PASS (14 existing + 8 new)

- [ ] **Step 5: Commit**

```bash
git add audit_project_settings/diff.py audit_project_settings/tests/test_diff.py
git commit -m "feat: add build_result and format_text to diff.py"
```

---

### Task 3: File output + main orchestration + README

**Files:**
- Modify: `audit_project_settings/diff.py` (append `write_outputs` + `main` + `if __name__` block)
- Modify: `audit_project_settings/tests/test_diff.py` (append integration tests)
- Modify: `audit_project_settings/README.md` (append diff section)

**Interfaces:**
- Consumes:
  - `load_audit(path: str) -> dict`
  - `collect_names(audit, resource) -> set[str]`
  - `find_missing_policies(audit_a, names_b) -> list[dict]`
  - `find_missing_profiles(audit_a, names_b) -> list[dict]`
  - `build_result(audit_a, audit_b, missing_policies, missing_profiles) -> dict`
  - `format_text(result) -> str`
- Produces:
  - `write_outputs(result: dict, text: str, output_dir: str, timestamp: str) -> tuple[str, str]` — writes `diff_audit.<timestamp>.json` and `.txt` to `output_dir`; creates `output_dir` if needed; returns `(json_path, txt_path)`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing integration tests**

Append to `audit_project_settings/tests/test_diff.py`:

```python
import json as _json
from pathlib import Path
from audit_project_settings.diff import main, write_outputs


def _valid_audit(namespace, project_uuid):
    return {
        "meta": {"namespace": namespace},
        "project": {"name": f"repo-{namespace}", "uuid": project_uuid},
        "namespaces": [
            {
                "namespace": namespace,
                "scope": "own",
                "policies": [
                    {"name": "Exc Policy", "policy_type": "POLICY_TYPE_EXCEPTION",
                     "applies": True, "reason": "all", "disabled": False,
                     "url": f"https://app/t/{namespace}/policies/pol1"},
                ],
                "scan_profiles": [
                    {"name": "Strict", "is_default": True, "applies": True, "reason": "all"},
                ],
            }
        ],
    }


# --- write_outputs ---

def test_write_outputs_creates_files(tmp_path):
    result = {"meta": {}, "missing_policies": [], "missing_scan_profiles": [], "summary": {}}
    text = "some text"
    json_path, txt_path = write_outputs(result, text, str(tmp_path / "reports"), "20260624_120000")
    assert Path(json_path).exists()
    assert Path(txt_path).exists()
    assert "diff_audit.20260624_120000.json" in json_path
    assert "diff_audit.20260624_120000.txt" in txt_path


def test_write_outputs_creates_output_dir(tmp_path):
    result = {"meta": {}, "missing_policies": [], "missing_scan_profiles": [], "summary": {}}
    out_dir = str(tmp_path / "new" / "nested" / "dir")
    write_outputs(result, "text", out_dir, "20260624_120000")
    assert Path(out_dir).exists()


def test_write_outputs_json_content(tmp_path):
    result = {"meta": {"source_a": {"namespace": "ns.a"}}, "missing_policies": [], "missing_scan_profiles": [], "summary": {"missing_policy_count": 0}}
    json_path, _ = write_outputs(result, "text", str(tmp_path), "20260624_120000")
    loaded = _json.loads(Path(json_path).read_text())
    assert loaded["meta"]["source_a"]["namespace"] == "ns.a"


# --- main ---

def test_main_creates_both_output_files(tmp_path):
    a_path = tmp_path / "audit_a.json"
    b_path = tmp_path / "audit_b.json"
    a_path.write_text(_json.dumps(_valid_audit("ns.a", "uuid-a")))
    b_path.write_text(_json.dumps(_valid_audit("ns.b", "uuid-b")))
    out_dir = str(tmp_path / "reports")
    rc = main([str(a_path), str(b_path), "--output-dir", out_dir])
    assert rc == 0
    assert len(list(Path(out_dir).glob("diff_audit.*.json"))) == 1
    assert len(list(Path(out_dir).glob("diff_audit.*.txt"))) == 1


def test_main_json_output_has_correct_schema(tmp_path):
    a_path = tmp_path / "audit_a.json"
    b_path = tmp_path / "audit_b.json"
    a_path.write_text(_json.dumps(_valid_audit("ns.a", "uuid-a")))
    b_path.write_text(_json.dumps(_valid_audit("ns.b", "uuid-b")))
    out_dir = str(tmp_path / "reports")
    main([str(a_path), str(b_path), "--output-dir", out_dir])
    json_file = next(Path(out_dir).glob("diff_audit.*.json"))
    result = _json.loads(json_file.read_text())
    assert result["meta"]["source_a"]["namespace"] == "ns.a"
    assert result["meta"]["source_b"]["namespace"] == "ns.b"
    assert "missing_policies" in result
    assert "missing_scan_profiles" in result
    assert "summary" in result


def test_main_detects_missing_policy(tmp_path):
    audit_a = _valid_audit("ns.a", "uuid-a")
    audit_b = {
        "meta": {"namespace": "ns.b"},
        "project": {"name": "repo-b", "uuid": "uuid-b"},
        "namespaces": [{"namespace": "ns.b", "scope": "own", "policies": [], "scan_profiles": []}],
    }
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(_json.dumps(audit_a))
    b_path.write_text(_json.dumps(audit_b))
    out_dir = str(tmp_path / "reports")
    main([str(a_path), str(b_path), "--output-dir", out_dir])
    json_file = next(Path(out_dir).glob("diff_audit.*.json"))
    result = _json.loads(json_file.read_text())
    assert result["summary"]["missing_policy_count"] == 1
    assert result["missing_policies"][0]["name"] == "Exc Policy"


def test_main_exits_1_on_missing_input_file(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main(["/nonexistent/a.json", "/nonexistent/b.json"])
    assert exc_info.value.code != 0


def test_main_prints_text_to_stdout(tmp_path, capsys):
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(_json.dumps(_valid_audit("ns.a", "uuid-a")))
    b_path.write_text(_json.dumps(_valid_audit("ns.b", "uuid-b")))
    main([str(a_path), str(b_path), "--output-dir", str(tmp_path / "reports")])
    captured = capsys.readouterr()
    assert "Diff:" in captured.out
    assert "Summary:" in captured.out
    assert "Output:" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest audit_project_settings/tests/test_diff.py -v -k "write_outputs or test_main"
```

Expected: `ImportError` — functions not yet defined

- [ ] **Step 3: Append `write_outputs`, `main`, and `if __name__` block to `diff.py`**

```python
def write_outputs(
    result: dict, text: str, output_dir: str, timestamp: str
) -> tuple[str, str]:
    """Write JSON and text files to output_dir. Creates the dir if needed."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base = f"diff_audit.{timestamp}"
    json_path = str(Path(output_dir) / f"{base}.json")
    txt_path = str(Path(output_dir) / f"{base}.txt")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)
    with open(txt_path, "w") as f:
        f.write(text)
        f.write("\n")
    return json_path, txt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diff two audit_project_settings JSON outputs — "
            "shows what A has that B is missing."
        )
    )
    parser.add_argument("audit_a", help="Path to source audit JSON (the reference project)")
    parser.add_argument("audit_b", help="Path to destination audit JSON (the target project)")
    parser.add_argument(
        "--output-dir",
        default="generated_reports",
        help="Directory for output files (default: generated_reports)",
    )
    args = parser.parse_args(argv)

    audit_a = load_audit(args.audit_a)
    audit_b = load_audit(args.audit_b)

    names_b_policies = collect_names(audit_b, "policies")
    names_b_profiles = collect_names(audit_b, "scan_profiles")

    missing_policies = find_missing_policies(audit_a, names_b_policies)
    missing_profiles = find_missing_profiles(audit_a, names_b_profiles)

    result = build_result(audit_a, audit_b, missing_policies, missing_profiles)
    text = format_text(result)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path, txt_path = write_outputs(result, text, args.output_dir, timestamp)

    print(text)
    print(f"\nOutput: {json_path}")
    print(f"        {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all diff tests**

```bash
pytest audit_project_settings/tests/test_diff.py -v
```

Expected: all 29 tests PASS (22 existing + 7 new)

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
pytest audit_project_settings/tests/ -v
```

Expected: all 59 tests PASS (30 from main + 29 from diff)

- [ ] **Step 6: Append diff section to `audit_project_settings/README.md`**

Append the following to the end of the file:

```markdown

---

## Diff: Comparing Two Projects

`diff.py` takes two audit JSON files (produced by `main.py`) and shows what policies and scan profiles are in A but missing from B — giving you a migration checklist.

### Usage

```
python diff.py <audit_a.json> <audit_b.json> [--output-dir <dir>]
```

| Argument | Required | Description |
|---|---|---|
| `audit_a` | Yes | Path to source audit JSON (the reference project) |
| `audit_b` | Yes | Path to destination audit JSON (the target project) |
| `--output-dir` | No | Output directory. Default: `generated_reports/` |

Both a JSON result and a text summary are always written. The text summary is also printed to the terminal.

### Typical migration workflow

```bash
# 1. Audit the source project
python main.py acme.backend.api a1b2c3d4e5f6a7b8c9d0e1f2 > audit_source.json

# 2. Audit the destination project
python main.py acme.newteam.api b2c3d4e5f6a7b8c9d0e1f2a3 > audit_dest.json

# 3. See what needs to be recreated in the destination
python diff.py audit_source.json audit_dest.json
```

### Output files

```
generated_reports/diff_audit.<timestamp>.json   # structured diff (pipeable)
generated_reports/diff_audit.<timestamp>.txt    # human-readable checklist
```

### Example terminal output

```
Diff: acme.backend.api (a1b2c3d4e5f6a7b8c9d0e1f2) → acme.newteam.api (b2c3d4e5f6a7b8c9d0e1f2a3)

Policies missing from B (2):
  POLICY_TYPE_ADMISSION (1):
    - Break the Build: Critical CVEs  [acme.backend] https://app.endorlabs.com/t/acme.backend/policies/...
  POLICY_TYPE_EXCEPTION (1):
    - Exception: Log4j  [acme]

Scan profiles missing from B (0): none

Summary: 2 missing policies, 0 missing scan profiles.
Output: generated_reports/diff_audit.20260624_103000.json
        generated_reports/diff_audit.20260624_103000.txt
```
```

- [ ] **Step 7: Commit**

```bash
git add audit_project_settings/diff.py audit_project_settings/tests/test_diff.py audit_project_settings/README.md
git commit -m "feat: add write_outputs, main, and README diff section to diff.py"
```
