import pandas as pd

import compute
from compute import AllocationParams


# --- language gate ---

def test_normalize_language_aliases():
    assert compute.normalize_language("Java") == "java"
    assert compute.normalize_language("C++") == "cpp"
    assert compute.normalize_language("C#") == "csharp"
    assert compute.normalize_language("golang") == "go"
    assert compute.normalize_language("TypeScript") == "typescript"


def test_normalize_language_unsupported_returns_none():
    assert compute.normalize_language("COBOL") is None
    assert compute.normalize_language("HTML") is None


def test_short_repo_name_strips_url_and_git():
    assert compute.short_repo_name("https://github.com/acme-platform/pr-agent-settings.git") == "pr-agent-settings"
    assert compute.short_repo_name("org/repo") == "repo"
    assert compute.short_repo_name("just-a-name") == "just-a-name"
    assert compute.short_repo_name("") == ""


def test_root_namespace_takes_first_segment():
    assert compute.root_namespace("acme-corp.acme-appdev") == "acme-corp"
    assert compute.root_namespace("acme.team.subproject") == "acme"
    assert compute.root_namespace("root-only") == "root-only"
    assert compute.root_namespace("") == ""


def test_supported_language_share_mixed():
    langs = {"Java": 800.0, "HTML": 200.0}
    assert compute.supported_language_share(langs) == 0.8


def test_supported_language_share_empty_is_zero():
    assert compute.supported_language_share({}) == 0.0
    assert compute.supported_language_share(None) == 0.0


def test_passes_language_gate_threshold():
    assert compute.passes_language_gate(0.5, 0.5) is True
    assert compute.passes_language_gate(0.49, 0.5) is False


def test_supported_kloc_only_counts_supported_bytes():
    langs = {"Java": 30000.0, "COBOL": 30000.0}  # 30 bytes/line default -> 1 KLOC supported
    assert compute.supported_kloc(langs) == 1.0


# --- cost model ---

def test_total_supported_kloc_sums_across_repos():
    maps = [{"Java": 30000.0}, {"Python": 60000.0, "HTML": 90000.0}]  # 1 + 2 KLOC supported
    assert compute.total_supported_kloc(maps) == 3.0


def test_total_supported_kloc_empty_is_zero():
    assert compute.total_supported_kloc([]) == 0.0


def test_monitored_version_counts_by_parent_project():
    versions = [
        {"meta": {"parent_uuid": "proj-a"}},
        {"meta": {"parent_uuid": "proj-a"}},
        {"meta": {"parent_uuid": "proj-b"}},
        {"meta": {}},  # no parent -> ignored
    ]
    assert compute.monitored_version_counts(versions) == {"proj-a": 2, "proj-b": 1}


def test_ai_sast_scanned_projects_detects_indexed_or_scanned():
    versions = [
        {"meta": {"parent_uuid": "indexed"},
         "scan_object": {"aisast_status": {"last_full_index_time": "2026-07-01T00:00:00Z"}}},
        {"meta": {"parent_uuid": "scanned"},
         "scan_object": {"aisast_status": {"last_scan_state": "AISAST_SCAN_STATE_SCAN_SUCCEEDED"}}},
        {"meta": {"parent_uuid": "sha-only"},
         "scan_object": {"aisast_status": {"last_full_index_sha": "abc123"}}},
        {"meta": {"parent_uuid": "never"},
         "scan_object": {"aisast_status": {"last_scan_state": "AISAST_SCAN_STATE_UNSPECIFIED"}}},
        {"meta": {"parent_uuid": "no-status"}, "scan_object": {}},
        {"meta": {"parent_uuid": "no-scan-object"}},
    ]
    assert compute.ai_sast_scanned_projects(versions) == {"indexed", "scanned", "sha-only"}


def test_ai_sast_scanned_projects_empty():
    assert compute.ai_sast_scanned_projects([]) == set()


def test_calibrate_cost_per_kloc_none_when_no_data():
    rate, conf = compute.calibrate_cost_per_kloc(total_spend=0.0, total_scanned_kloc=0.0)
    assert rate is None
    assert conf == "none"


def test_calibrate_cost_per_kloc_low_and_medium():
    rate, conf = compute.calibrate_cost_per_kloc(total_spend=50.0, total_scanned_kloc=50.0)
    assert rate == 1.0
    assert conf == "low"
    _, conf2 = compute.calibrate_cost_per_kloc(total_spend=200.0, total_scanned_kloc=200.0)
    assert conf2 == "medium"


def test_monitored_version_multiplier():
    assert compute.monitored_version_multiplier(1) == 1.0
    assert compute.monitored_version_multiplier(3, k=0.3) == 1.6
    assert compute.monitored_version_multiplier(0) == 1.0  # floored at 1 version


def test_size_bucket_cost_bands():
    assert compute.size_bucket_cost(5) == 2.0
    assert compute.size_bucket_cost(40) == 6.0
    assert compute.size_bucket_cost(150) == 20.0
    assert compute.size_bucket_cost(500) == compute.SIZE_BUCKET_LARGE_COST


def test_estimate_tier1_cost_uses_rate_and_multiplier():
    # 10 KLOC * $2/KLOC * (1 + 0.3*(2-1)) = 20 * 1.3 = 26
    assert compute.estimate_tier1_cost(kloc=10.0, rate=2.0, monitored_versions=2, k=0.3) == 26.0


def test_estimate_tier1_cost_falls_back_to_buckets_when_uncalibrated():
    # rate None, 5 KLOC -> bucket $2, single version -> 2.0
    assert compute.estimate_tier1_cost(kloc=5.0, rate=None, monitored_versions=1) == 2.0


def test_estimate_tier2_cost_scales_with_findings():
    assert compute.estimate_tier2_cost(10, per_finding=0.02) == 0.2
    assert compute.estimate_tier2_cost(0) == 0.0


# --- value scoring ---

def test_normalize_series_min_max():
    s = pd.Series([0.0, 5.0, 10.0])
    result = compute.normalize_series(s)
    assert list(result) == [0.0, 0.5, 1.0]


def test_normalize_series_all_equal_is_zero():
    s = pd.Series([4.0, 4.0, 4.0])
    assert list(compute.normalize_series(s)) == [0.0, 0.0, 0.0]


def test_value_score_weighted_blend():
    components = {"activity": 1.0, "findings": 0.0, "release": 0.5}
    weights = {"activity": 1.0, "findings": 1.0, "release": 2.0}
    # (1*1 + 0*1 + 0.5*2) / 4 = 2/4 = 0.5
    assert compute.value_score(components, weights) == 0.5


# --- allocator ---

def _repo(project, langs, mv=1, activity=0.0, findings=0, release=0.0):
    return {"project": project, "languages": langs, "monitored_versions": mv,
            "activity": activity, "findings": findings, "release_signal": release}


def test_allocate_language_gated_repo_is_tier3():
    repos = pd.DataFrame([_repo("legacy", {"COBOL": 1000.0})])
    params = AllocationParams(budget=1000.0, cost_rate=1.0)
    result = compute.allocate_tiers(repos, params)
    assert result.iloc[0]["tier"] == 3
    assert "supported-language" in result.iloc[0]["rationale"]


def test_allocate_promotes_high_value_to_tier1_within_budget():
    repos = pd.DataFrame([
        _repo("crown", {"Java": 30000.0}, mv=1, activity=10, findings=5, release=3),
        _repo("quiet", {"Java": 30000.0}, mv=1, activity=0, findings=0, release=0),
    ])
    params = AllocationParams(budget=1000.0, safety_margin=0.0, cost_rate=1.0)
    result = compute.allocate_tiers(repos, params).set_index("project")
    assert result.loc["crown", "tier"] == 1
    assert result.loc["crown", "rank"] == 1


def test_allocate_respects_budget_cap_demotes_overflow():
    # Two eligible repos, budget only fits one Tier 1 baseline.
    repos = pd.DataFrame([
        _repo("a", {"Java": 30000.0}, activity=10, findings=1, release=1),
        _repo("b", {"Java": 30000.0}, activity=1, findings=0, release=0),
    ])
    # kloc=1 each, rate=$5 -> cost $5 each; budget 6, margin 0 -> only one fits
    params = AllocationParams(budget=6.0, safety_margin=0.0, cost_rate=5.0)
    result = compute.allocate_tiers(repos, params).set_index("project")
    assert result.loc["a", "tier"] == 1  # higher value promoted first
    assert result.loc["b", "tier"] == 3  # no findings, and budget exhausted


def test_allocate_eligible_with_findings_gets_tier2_when_not_promoted():
    repos = pd.DataFrame([
        _repo("a", {"Java": 30000.0}, activity=10, findings=1, release=1),
        _repo("b", {"Java": 30000.0}, activity=1, findings=8, release=0),
    ])
    # a costs $5 (fits in Tier1); b costs $5 (doesn't fit Tier1 under cap) but has findings -> Tier 2
    params = AllocationParams(budget=6.0, safety_margin=0.0, cost_rate=5.0)
    result = compute.allocate_tiers(repos, params).set_index("project")
    assert result.loc["a", "tier"] == 1
    assert result.loc["b", "tier"] == 2


def test_allocate_empty_frame_returns_empty_with_columns():
    repos = pd.DataFrame(columns=["project", "languages", "monitored_versions", "activity", "findings", "release_signal"])
    result = compute.allocate_tiers(repos, AllocationParams(budget=100.0))
    assert result.empty
    assert "tier" in result.columns


def test_allocation_summary_counts_and_headroom():
    repos = pd.DataFrame([
        _repo("a", {"Java": 30000.0}, activity=10, findings=1, release=1),
        _repo("b", {"COBOL": 30000.0}),
    ])
    params = AllocationParams(budget=100.0, safety_margin=0.0, cost_rate=1.0)
    allocated = compute.allocate_tiers(repos, params)
    summary = compute.allocation_summary(allocated, params)
    assert summary["tier1_count"] + summary["tier2_count"] + summary["tier3_count"] == 2
    assert summary["tier3_count"] >= 1  # COBOL repo gated
    assert summary["usable_budget"] == 100.0
