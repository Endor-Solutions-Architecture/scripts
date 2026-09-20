from __future__ import annotations

from classify import (
    classify_finding,
    classify_outcome,
    classify_trajectory,
    derive_fixable,
    derive_reachability,
    extract_policy_name,
    extract_pr_number,
    is_cleared,
)


def test_pr_number_from_context_tags():
    assert extract_pr_number({"context": {"tags": ["pr=42"]}, "meta": {"tags": []}}) == "42"


def test_pr_number_missing():
    assert extract_pr_number({"context": {"tags": ["branch=main"]}, "meta": {}}) is None


def test_outcome_warn_beats_empty_block():
    assert classify_outcome({"spec": {"warning_findings": ["a"], "blocking_findings": []}}) == "warn"


def test_outcome_block_when_no_warn():
    assert classify_outcome({"spec": {"warning_findings": [], "blocking_findings": ["b"]}}) == "block"


def test_outcome_clean():
    assert classify_outcome({"spec": {}}) == "clean"


def test_finding_ai_sast_before_sast():
    f = {"spec": {"finding_categories": ["FINDING_CATEGORY_SAST"],
                  "finding_tags": ["FINDING_TAGS_AI"]}}
    assert classify_finding(f) == "AI SAST"


def test_finding_secrets():
    f = {"spec": {"finding_categories": ["FINDING_CATEGORY_SECRETS"]}}
    assert classify_finding(f) == "Secrets"


def test_reachability_and_fix():
    tags = ["FINDING_TAGS_REACHABLE_FUNCTION", "FINDING_TAGS_FIX_AVAILABLE"]
    assert derive_reachability(tags) == "Reachable"
    assert derive_fixable(tags) == "Yes"


def test_trajectory_buckets():
    assert classify_trajectory(1, 3, 3) == "single_scan"
    assert classify_trajectory(2, 3, 1) == "acted"
    assert classify_trajectory(2, 3, 0) == "acted"
    assert classify_trajectory(2, 1, 1) == "still_open"
    assert classify_trajectory(2, 1, 2) == "still_open"
    assert is_cleared(0, "acted") is True
    assert is_cleared(1, "acted") is False
    assert is_cleared(0, "single_scan") is False


def test_policy_name_from_list():
    scan = {"spec": {"triggered_policies": [{"meta": {"name": "SCA warn"}}]}}
    assert extract_policy_name(scan) == "SCA warn"
