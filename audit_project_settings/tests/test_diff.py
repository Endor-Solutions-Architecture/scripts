import json
import json as _json
from pathlib import Path

import pytest

from audit_project_settings.diff import (
    build_result,
    collect_names,
    find_missing_policies,
    find_missing_profiles,
    format_text,
    load_audit,
    main,
    write_outputs,
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
    assert "Output:" not in Path(txt_path).read_text()


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
