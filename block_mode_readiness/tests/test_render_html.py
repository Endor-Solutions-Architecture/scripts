from __future__ import annotations

from analyze import analyze
from helpers import full_sample_snapshot
from render_html import build_dashboard_payload, write_html


def test_dashboard_payload_contains_consolidated_readiness_data():
    snapshot = full_sample_snapshot()
    analysis = analyze(snapshot, snapshot_count=2)

    payload = build_dashboard_payload(analysis, snapshot)

    assert payload["meta"]["namespace"] == "example-corp"
    assert payload["meta"]["snapshot_count"] == 2
    assert payload["summary"]["checks_total"] == 8
    assert payload["summary"]["checks_warn"] == 6
    assert payload["summary"]["checks_clean"] == 2
    assert payload["summary"]["would_have_blocked_pct"] == 75.0
    assert payload["summary"]["zero_warn_repos"] == 1
    assert payload["daily"][0] == {
        "date": "2026-03-01",
        "checks": 1,
        "clean": 0,
        "warn": 1,
        "block": 0,
        "warn_rate": 100.0,
    }
    assert {row["project_name"] for row in payload["repos"]} == {
        "org/alpha",
        "org/beta",
    }
    assert len(payload["pr_checks"]) == 8
    assert len(payload["trajectories"]) == 4
    assert payload["policies"][0]["name"] == "Warn on critical"
    assert payload["policies"][0]["state"] == "enabled"
    assert payload["capabilities"] == {
        "pr_comments": False,
        "merge_status": False,
        "ci_duration": False,
        "remediation_status": False,
        "pilot_plan_progress": False,
    }


def test_dashboard_payload_includes_false_positive_labels_when_supplied():
    snapshot = full_sample_snapshot()
    first = analyze(snapshot).fp_rows[0]
    labels = [
        {
            "finding_uuid": first["finding_uuid"],
            "scan_result_uuid": first["scan_result_uuid"],
            "fp": "yes",
            "reason": "test fixture",
        }
    ]

    payload = build_dashboard_payload(analyze(snapshot, labels=labels), snapshot)

    assert payload["false_positives"]["available"] is True
    assert payload["false_positives"]["per_finding_rate"] == 100.0
    assert payload["false_positives"]["per_finding_counts"] == [1, 1]
    assert any(row["fp"] == "yes" for row in payload["findings"])


def test_write_html_is_one_safe_self_contained_file(tmp_path):
    snapshot = full_sample_snapshot()
    snapshot.meta.customer = '</script><script>alert("x")</script>'
    snapshot.projects["p-alpha"].full_name = '<img src=x onerror=alert("x")>'
    path = tmp_path / "readiness_dashboard.html"

    write_html(analyze(snapshot), snapshot, path)

    html = path.read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "<title>Block Mode Readiness Dashboard</title>" in html
    assert 'id="dashboard-data"' in html
    assert 'id="tab-overview"' in html
    assert 'id="tab-coverage"' in html
    assert 'id="tab-trends"' in html
    assert 'id="tab-developer"' in html
    assert 'id="tab-findings"' in html
    assert 'id="tab-policies"' in html
    assert 'id="tab-checks"' in html
    assert 'id="tab-methodology"' in html
    assert "<script src=" not in html.lower()
    assert '<link rel="stylesheet"' not in html.lower()
    assert "https://cdn" not in html.lower()
    assert '</script><script>alert("x")</script>' not in html
    assert '<img src=x onerror=alert("x")>' not in html


def test_write_html_contains_explicit_empty_and_unlabeled_states(tmp_path):
    snapshot = full_sample_snapshot()
    snapshot.scans = {}
    snapshot.findings = {}
    path = tmp_path / "readiness_dashboard.html"

    write_html(analyze(snapshot), snapshot, path)

    html = path.read_text(encoding="utf-8")
    assert "No PR checks match this snapshot." in html
    assert "False-positive rates require returned labels." in html
