import csv
import json
from io import StringIO
from pathlib import Path

import pytest

from dependency_resolution_summary.main import (
    CSV_HEADERS,
    clean_description,
    extract_error_message,
    extract_first_sentence_smart,
    fetch_all_projects,
    get_error_message_from_analysis,
    process_project,
    resolve_token,
    write_csv,
)


def test_extract_first_sentence_stops_at_period_then_capital():
    text = "Tool not found. Install it and retry."
    assert extract_first_sentence_smart(text) == "Tool not found."


def test_extract_first_sentence_does_not_split_on_version_numbers():
    text = "Reference assemblies for .NETFramework v4.5.2 were not found."
    assert extract_first_sentence_smart(text) == text


def test_extract_first_sentence_returns_full_text_when_no_sentence_break():
    text = "single phrase no period"
    assert extract_first_sentence_smart(text) == text


def test_extract_first_sentence_handles_trailing_period():
    text = "Single sentence."
    assert extract_first_sentence_smart(text) == "Single sentence."


def test_clean_description_empty():
    assert clean_description("") == ""
    assert clean_description(None) == ""


def test_clean_description_collapses_whitespace_and_strips():
    assert clean_description("  hello\tworld\r\n  ") == "hello world"


def test_clean_description_keeps_last_two_lines_when_multiline():
    text = "first\nsecond\nthird\nfourth"
    assert clean_description(text) == "third fourth"


def test_clean_description_passes_short_text_through():
    assert clean_description("a\nb") == "a b"


def test_error_message_uses_fixable_notes_for_non_toolchain():
    analysis = {"error_category": "ERROR_CATEGORY_DEPENDENCY", "fixable_notes": "  add registry config  "}
    assert get_error_message_from_analysis(analysis) == "add registry config"


def test_error_message_uses_first_sentence_of_matching_snippet_for_toolchain():
    analysis = {
        "error_category": "ERROR_CATEGORY_TOOLCHAIN",
        "matching_snippet": "Tool not found. Install with brew.",
    }
    assert get_error_message_from_analysis(analysis) == "Tool not found."


def test_error_message_returns_empty_when_no_useful_fields():
    assert get_error_message_from_analysis({"error_category": "ERROR_CATEGORY_OTHER"}) == ""
    assert get_error_message_from_analysis({}) == ""


def test_error_message_toolchain_with_no_snippet_returns_empty():
    assert get_error_message_from_analysis({"error_category": "ERROR_CATEGORY_TOOLCHAIN"}) == ""


def test_extract_error_prefers_call_graph_then_resolved_then_unresolved():
    errors = {
        "call_graph": {"error_analysis": [{"error_category": "X", "fixable_notes": "from call_graph"}]},
        "resolved": {"error_analysis": [{"error_category": "X", "fixable_notes": "from resolved"}]},
        "unresolved": {"error_analysis": [{"error_category": "X", "fixable_notes": "from unresolved"}]},
    }
    assert extract_error_message(errors) == "from call_graph"


def test_extract_error_falls_through_to_next_bucket_when_first_is_empty():
    errors = {
        "call_graph": {"error_analysis": [{}]},
        "resolved": {"error_analysis": [{"error_category": "X", "fixable_notes": "second choice"}]},
    }
    assert extract_error_message(errors) == "second choice"


def test_extract_error_falls_back_to_description_when_no_analysis():
    errors = {
        "unresolved": {"description": "line one\nline two\nlast line"},
    }
    # last 2 lines, joined and whitespace-collapsed
    assert extract_error_message(errors) == "line two last line"


def test_extract_error_returns_empty_when_nothing_useful():
    assert extract_error_message({}) == ""
    assert extract_error_message({"call_graph": {}}) == ""


def test_extract_error_description_in_earlier_bucket_beats_analysis_in_later_bucket():
    errors = {
        "call_graph": {
            "error_analysis": [{"error_category": "ERROR_CATEGORY_OTHER"}],
            "description": "call_graph fallback",
        },
        "resolved": {"error_analysis": [{"error_category": "X", "fixable_notes": "resolved note"}]},
    }
    assert extract_error_message(errors) == "call_graph fallback"


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_process_project_categorizes_dependency_resolution_issues_when_failed_packages():
    raw = _load("sample_query_response.json")
    row = process_project(raw)

    assert row["uuid"] == "proj-1"
    assert row["namespace"] == "acme.team-a"
    assert row["project_name"] == "https://github.com/acme/repo.git"
    assert row["total_packages"] == 10
    assert row["dependency_resolution_success"] == 9
    assert row["dependency_resolution_failed"] == 1
    assert row["reachability_success"] == 8
    assert row["reachability_failed"] == 2
    assert row["dependency_resolution_percentage"] == 90.0
    assert row["reachability_percentage"] == 80.0
    assert row["category"] == "dependency_resolution_issues"
    assert row["reachability_strategy"] == ""  # only set for full_success / reachability_issues_only
    # Two distinct error notes, sorted alphabetically, joined by " | "
    assert row["error_notes"] == "Configure registry | Toolchain missing."
    assert row["project_url"] == (
        "https://app.endorlabs.com/t/acme.team-a/projects/proj-1"
        "/versions/default/inventory/packages"
    )
    assert row["tags"] == []


def test_process_project_full_success_with_precomputed_strategy():
    raw = {
        "uuid": "proj-2",
        "tenant_meta": {"namespace": "acme"},
        "meta": {"name": "x", "tags": ["t"], "references": {
            "TotalPackagesCount": {"count_response": {"count": 5}},
            "DependencyResolutionSuccessCount": {"count_response": {"count": 5}},
            "DependencyResolutionFailedCount": {"count_response": {"count": 0}},
            "ReachabilitySuccessCount": {"count_response": {"count": 5}},
            "ReachabilityFailedCount": {"count_response": {"count": 0}},
            "PackageDetails": {"list": {"objects": [
                {"spec": {"precomputed_call_graph_state": "PRECOMPUTED_STATE_SUCCESS"}},
                {"spec": {"precomputed_call_graph_state": "PRECOMPUTED_STATE_NONE"}},
            ]}},
        }},
    }
    row = process_project(raw)
    assert row["category"] == "full_success"
    assert row["reachability_strategy"] == "PRE-COMPUTED"
    assert row["error_notes"] == ""
    assert row["dependency_resolution_percentage"] == 100.0


def test_process_project_full_success_with_full_strategy():
    raw = {
        "uuid": "proj-3",
        "tenant_meta": {"namespace": "acme"},
        "meta": {"name": "x", "tags": [], "references": {
            "TotalPackagesCount": {"count_response": {"count": 1}},
            "DependencyResolutionSuccessCount": {"count_response": {"count": 1}},
            "DependencyResolutionFailedCount": {"count_response": {"count": 0}},
            "ReachabilitySuccessCount": {"count_response": {"count": 1}},
            "ReachabilityFailedCount": {"count_response": {"count": 0}},
            "PackageDetails": {"list": {"objects": [
                {"spec": {"precomputed_call_graph_state": "PRECOMPUTED_STATE_NONE"}},
            ]}},
        }},
    }
    row = process_project(raw)
    assert row["category"] == "full_success"
    assert row["reachability_strategy"] == "FULL"


def test_process_project_zero_packages_yields_zero_percentages():
    raw = {
        "uuid": "proj-4",
        "tenant_meta": {"namespace": "acme"},
        "meta": {"name": "x", "tags": [], "references": {
            "TotalPackagesCount": {"count_response": {"count": 0}},
            "DependencyResolutionSuccessCount": {"count_response": {"count": 0}},
            "DependencyResolutionFailedCount": {"count_response": {"count": 0}},
            "ReachabilitySuccessCount": {"count_response": {"count": 0}},
            "ReachabilityFailedCount": {"count_response": {"count": 0}},
            "PackageDetails": {"list": {"objects": []}},
        }},
    }
    row = process_project(raw)
    assert row["dependency_resolution_percentage"] == 0
    assert row["reachability_percentage"] == 0
    assert row["category"] == "full_success"
    assert row["reachability_strategy"] == "FULL"


def test_process_project_reachability_issues_only_category():
    raw = {
        "uuid": "proj-5",
        "tenant_meta": {"namespace": "acme"},
        "meta": {"name": "x", "tags": [], "references": {
            "TotalPackagesCount": {"count_response": {"count": 4}},
            "DependencyResolutionSuccessCount": {"count_response": {"count": 4}},
            "DependencyResolutionFailedCount": {"count_response": {"count": 0}},
            "ReachabilitySuccessCount": {"count_response": {"count": 3}},
            "ReachabilityFailedCount": {"count_response": {"count": 1}},
            "PackageDetails": {"list": {"objects": [
                {"spec": {"resolution_errors": {"call_graph": {"description": "boom"}}}},
            ]}},
        }},
    }
    row = process_project(raw)
    assert row["category"] == "reachability_issues_only"
    assert row["reachability_strategy"] == "FULL"
    assert row["error_notes"] == "boom"


def test_csv_headers_match_ewok_byte_for_byte():
    assert CSV_HEADERS == [
        "Namespace",
        "Project UUID",
        "Project Name",
        "Project URL",
        "Total Packages",
        "Dependency Resolution Success",
        "Dependency Resolution Failed",
        "Reachability Success",
        "Reachability Failed",
        "Dependency Resolution %",
        "Reachability %",
        "Category",
        "Reachability Strategy",
        "Error Notes",
        "Tags",
    ]


def test_write_csv_renders_one_row_per_project_with_tags_as_list_literal(tmp_path):
    rows = [{
        "namespace": "acme",
        "uuid": "u1",
        "project_name": "p",
        "project_url": "https://app.endorlabs.com/t/acme/projects/u1/versions/default/inventory/packages",
        "total_packages": 1,
        "dependency_resolution_success": 1,
        "dependency_resolution_failed": 0,
        "reachability_success": 1,
        "reachability_failed": 0,
        "dependency_resolution_percentage": 100.0,
        "reachability_percentage": 100.0,
        "category": "full_success",
        "reachability_strategy": "FULL",
        "error_notes": "",
        "tags": ["prod", "java"],
    }]
    out = tmp_path / "out.csv"
    write_csv(rows, str(out))

    with out.open() as f:
        content = f.read()
    reader = csv.reader(StringIO(content))
    parsed = list(reader)

    assert parsed[0] == CSV_HEADERS
    assert parsed[1][0] == "acme"
    assert parsed[1][1] == "u1"
    assert parsed[1][-1] == "['prod', 'java']"  # list literal, matches ewok
    assert parsed[1][-2] == ""  # error_notes empty


class _StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


def test_fetch_all_projects_pages_until_no_next_page_token(monkeypatch):
    pages = [
        {"spec": {"query_response": {"list": {
            "objects": [{"uuid": "p1"}, {"uuid": "p2"}],
            "response": {"next_page_token": 2},
        }}}},
        {"spec": {"query_response": {"list": {
            "objects": [{"uuid": "p3"}],
            "response": {"next_page_token": None},
        }}}},
    ]
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        import copy as _copy
        calls.append({"url": url, "body": _copy.deepcopy(json)})
        return _StubResponse(pages[len(calls) - 1])

    monkeypatch.setattr("dependency_resolution_summary.main.requests.post", fake_post)

    query = {"spec": {"query_spec": {"list_parameters": {}}}}
    projects = fetch_all_projects(
        api_url="https://api.example",
        namespace="ns",
        token="tok",
        query=query,
        page_size=100,
    )

    assert [p["uuid"] for p in projects] == ["p1", "p2", "p3"]
    assert calls[0]["url"] == "https://api.example/v1/namespaces/ns/queries"
    assert calls[0]["body"]["spec"]["query_spec"]["list_parameters"]["page_size"] == 100
    assert "page_token" not in calls[0]["body"]["spec"]["query_spec"]["list_parameters"]
    assert calls[1]["body"]["spec"]["query_spec"]["list_parameters"]["page_token"] == 2


def test_fetch_all_projects_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        "dependency_resolution_summary.main.requests.post",
        lambda *a, **kw: _StubResponse({"error": "forbidden"}, status_code=403),
    )
    with pytest.raises(RuntimeError, match="HTTP 403"):
        fetch_all_projects(
            "https://api.example",
            "ns",
            "tok",
            {"spec": {"query_spec": {"list_parameters": {}}}},
        )


def test_fetch_all_projects_does_not_mutate_caller_query(monkeypatch):
    pages = [{"spec": {"query_response": {"list": {"objects": [], "response": {"next_page_token": None}}}}}]

    def fake_post(url, json=None, headers=None, timeout=None):
        return _StubResponse(pages[0])

    monkeypatch.setattr("dependency_resolution_summary.main.requests.post", fake_post)

    query = {"spec": {"query_spec": {"list_parameters": {}}}}
    fetch_all_projects("https://api.example", "ns", "tok", query, page_size=42)
    assert query == {"spec": {"query_spec": {"list_parameters": {}}}}


def test_resolve_token_prefers_explicit(monkeypatch):
    monkeypatch.delenv("ENDOR_TOKEN", raising=False)
    assert resolve_token(explicit="abc") == "abc"


def test_resolve_token_uses_env_when_explicit_not_set(monkeypatch):
    monkeypatch.setenv("ENDOR_TOKEN", "from_env")
    assert resolve_token(explicit=None) == "from_env"


def test_resolve_token_falls_back_to_endorctl(monkeypatch):
    monkeypatch.delenv("ENDOR_TOKEN", raising=False)

    def fake_run(cmd, capture_output=True, text=True, check=True):
        class _R:
            stdout = "jwt-token-here\n"
        return _R()

    monkeypatch.setattr("dependency_resolution_summary.main.subprocess.run", fake_run)
    assert resolve_token(explicit=None) == "jwt-token-here"
