from __future__ import annotations

from analyze import analyze
from helpers import full_sample_snapshot


def test_would_have_blocked_rate():
    a = analyze(full_sample_snapshot())
    assert a.checks_total == 8
    assert a.checks_warn == 6
    assert a.checks_block == 0
    assert a.would_have_blocked_pct == 75.0


def test_section_b_includes_zero_warn_repo():
    a = analyze(full_sample_snapshot())
    names = {r.project_name: r for r in a.repos}
    assert names["org/beta"].checks == 0
    assert names["org/beta"].warns == 0
    assert names["org/alpha"].warns == 6


def test_section_d_buckets():
    a = analyze(full_sample_snapshot())
    by_pr = {t.pr_number: t.classification for t in a.trajectories}
    assert by_pr["10"] == "acted"
    assert by_pr["11"] == "still_open"
    assert by_pr["12"] == "single_scan"
    assert by_pr["13"] == "acted"
    assert "14" not in by_pr
    assert a.d_acted == 2
    assert a.d_still_open == 1
    assert a.d_single_scan == 1
    assert a.d_cleared == 1
    assert a.d_warned_prs == 4


def test_mark_date_split():
    a = analyze(full_sample_snapshot())
    split = a.mark_splits[0]
    assert split.key == "sast"
    assert split.before_total == 7
    assert split.before_warn == 5
    assert split.after_total == 1
    assert split.after_warn == 1
    assert split.before_block == 0
    assert split.after_block == 0


def test_mark_date_split_counts_blocks():
    snap = full_sample_snapshot()
    snap.scans["s8"].outcome = "block"
    snap.scans["s8"].blocking_finding_ids = ["f-block"]

    split = analyze(snap).mark_splits[0]

    assert split.before_block == 1
    assert split.after_block == 0


def test_fp_rows_blank_and_clean_scans_in_pr_checks():
    a = analyze(full_sample_snapshot())
    assert len(a.pr_check_rows) == 8
    assert all(r["fp"] == "" and r["reason"] == "" for r in a.fp_rows)
    assert any(r["outcome"] == "clean" for r in a.pr_check_rows)
    assert a.gate1_per_finding is None


def test_labels_join_and_unmatched():
    snap = full_sample_snapshot()
    a0 = analyze(snap)
    row = a0.fp_rows[0]
    labels = [
        {"finding_uuid": row["finding_uuid"], "scan_result_uuid": row["scan_result_uuid"],
         "fp": "yes", "reason": "noise"},
        {"finding_uuid": "missing", "scan_result_uuid": "missing", "fp": "no", "reason": ""},
    ]
    a = analyze(snap, labels=labels)
    matched = [r for r in a.fp_rows if r["fp"] == "yes"]
    assert len(matched) == 1
    assert matched[0]["reason"] == "noise"
    assert len(a.unmatched_labels) == 1
    assert a.gate1_per_finding == 100.0


def test_gate1_mixed_yes_no():
    snap = full_sample_snapshot()
    a0 = analyze(snap)
    labels = [
        {"finding_uuid": a0.fp_rows[0]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[0]["scan_result_uuid"], "fp": "yes", "reason": ""},
        {"finding_uuid": a0.fp_rows[1]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[1]["scan_result_uuid"], "fp": "no", "reason": ""},
    ]
    a = analyze(snap, labels=labels)
    assert a.gate1_per_finding == 50.0
    assert a.gate1_per_finding_counts == (1, 2)


def test_gate1_per_pr_and_by_type():
    snap = full_sample_snapshot()
    a0 = analyze(snap)
    labels = [
        {"finding_uuid": a0.fp_rows[0]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[0]["scan_result_uuid"], "fp": "yes", "reason": ""},
        {"finding_uuid": a0.fp_rows[1]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[1]["scan_result_uuid"], "fp": "no", "reason": ""},
    ]
    a = analyze(snap, labels=labels)
    assert a.gate1_per_pr == 0.0
    assert a.gate1_per_pr_counts == (0, 1)
    assert a.gate1_by_type == {"SAST": 0.0, "Vulnerability": 100.0}
    assert a.gate1_by_type_counts == {
        "SAST": (0, 1),
        "Vulnerability": (1, 1),
    }
    assert a.gate1_by_type_per_pr == {
        "SAST": 0.0,
        "Vulnerability": 100.0,
    }
    assert a.gate1_by_type_per_pr_counts == {
        "SAST": (0, 1),
        "Vulnerability": (1, 1),
    }


def test_gate1_unsure_excluded_and_unmatched_preserves_rows():
    snap = full_sample_snapshot()
    a0 = analyze(snap)
    unmatched = {
        "finding_uuid": "missing",
        "scan_result_uuid": "missing",
        "fp": "no",
        "reason": "x",
    }
    labels = [
        {"finding_uuid": a0.fp_rows[0]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[0]["scan_result_uuid"], "fp": " YES ", "reason": ""},
        {"finding_uuid": a0.fp_rows[1]["finding_uuid"],
         "scan_result_uuid": a0.fp_rows[1]["scan_result_uuid"], "fp": "unsure", "reason": ""},
        unmatched,
    ]
    a = analyze(snap, labels=labels)
    assert len(a.fp_rows) == len(a0.fp_rows)
    assert a.unmatched_labels == [unmatched]
    assert a.gate1_per_finding == 100.0
    assert a.gate1_per_pr == 100.0
    assert a.gate1_by_type == {"Vulnerability": 100.0}
    assert a.checks_total == a0.checks_total
    assert a.checks_warn == a0.checks_warn
    assert a.d_acted == a0.d_acted
    assert a.d_still_open == a0.d_still_open
    assert a.d_single_scan == a0.d_single_scan
    assert a.d_cleared == a0.d_cleared
    assert a.d_warned_prs == a0.d_warned_prs
