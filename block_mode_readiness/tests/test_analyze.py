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


def test_fp_rows_blank_and_clean_scans_in_pr_checks():
    a = analyze(full_sample_snapshot())
    assert len(a.pr_check_rows) == 8
    assert all(r["fp"] == "" and r["reason"] == "" for r in a.fp_rows)
    assert any(r["outcome"] == "clean" for r in a.pr_check_rows)
    assert a.gate1_per_finding is None
