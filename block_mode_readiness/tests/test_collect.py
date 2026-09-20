from __future__ import annotations

import pytest

from collect import CollectError, collect


def _list(objects):
    return {"list": {"objects": objects}}


def test_collect_drops_ci_without_pr_and_keeps_clean():
    calls = []

    def runner(args, namespace, timeout=120):
        calls.append(args)
        kind = args[args.index("-r") + 1]
        if kind == "Project":
            return _list([{
                "uuid": "p-alpha",
                "meta": {"tags": ["rollout-wave-1"]},
                "tenant_meta": {"namespace": "example-corp"},
                "spec": {"git": {"full_name": "org/alpha",
                                 "http_clone_url": "https://github.com/org/alpha.git"}},
            }])
        if kind == "Policy":
            return _list([{
                "uuid": "pol1",
                "meta": {"name": "Warn critical"},
                "spec": {"policy_type": "POLICY_TYPE_ADMISSION",
                         "disable": False,
                         "project_selector": ["rollout-wave-1"]},
            }])
        if kind == "ScanResult":
            filt = args[args.index("--filter") + 1]
            assert "CONTEXT_TYPE_CI_RUN" in filt
            assert "warning_findings exists" not in filt
            return _list([
                {
                    "uuid": "s-warn",
                    "meta": {"create_time": "2026-03-01T00:00:00Z", "parent_uuid": "p-alpha",
                             "tags": []},
                    "tenant_meta": {"namespace": "example-corp"},
                    "context": {"tags": ["pr=1"]},
                    "spec": {"status": "ok", "warning_findings": ["f1"], "blocking_findings": []},
                },
                {
                    "uuid": "s-clean",
                    "meta": {"create_time": "2026-03-02T00:00:00Z", "parent_uuid": "p-alpha",
                             "tags": ["pr=2"]},
                    "tenant_meta": {"namespace": "example-corp"},
                    "context": {"tags": []},
                    "spec": {"status": "ok", "warning_findings": [], "blocking_findings": []},
                },
                {
                    "uuid": "s-ci",
                    "meta": {"create_time": "2026-03-03T00:00:00Z", "parent_uuid": "p-alpha",
                             "tags": []},
                    "tenant_meta": {"namespace": "example-corp"},
                    "context": {"tags": ["branch=main"]},
                    "spec": {"status": "ok", "warning_findings": ["f1"], "blocking_findings": []},
                },
            ])
        if kind == "Finding":
            return _list([{
                "uuid": "f1",
                "meta": {"name": "cve", "description": "a finding"},
                "tenant_meta": {"namespace": "example-corp"},
                "spec": {"level": "FINDING_LEVEL_CRITICAL",
                         "finding_categories": ["FINDING_CATEGORY_VULNERABILITY"],
                         "finding_tags": ["FINDING_TAGS_FIX_AVAILABLE"],
                         "finding_metadata": {"vulnerability": {"meta": {"name": "CVE-2026-0001"}}}},
            }])
        raise AssertionError(kind)

    snap = collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert set(snap.scans) == {"s-warn", "s-clean"}
    assert snap.scans["s-clean"].outcome == "clean"
    assert snap.meta.ci_runs_dropped_no_pr == 1
    assert "f1" in snap.findings


def test_collect_zero_projects_does_not_list_scans():
    kinds = []

    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        kinds.append(kind)
        return _list([])

    with pytest.raises(CollectError, match="no projects"):
        collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert kinds == ["Project"]


def test_collect_retries_then_raises():
    n = {"ScanResult": 0}

    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        if kind == "Project":
            return _list([{
                "uuid": "p-alpha",
                "meta": {"tags": ["rollout-wave-1"]},
                "tenant_meta": {"namespace": "example-corp"},
                "spec": {"git": {"full_name": "org/alpha", "http_clone_url": ""}},
            }])
        if kind == "Policy":
            return _list([])
        if kind == "ScanResult":
            n["ScanResult"] += 1
            raise CollectError("boom", command=args)
        return _list([])

    with pytest.raises(CollectError):
        collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert n["ScanResult"] == 2


def _tagged_project():
    return {
        "uuid": "p-alpha",
        "meta": {"tags": ["rollout-wave-1"]},
        "tenant_meta": {"namespace": "example-corp"},
        "spec": {"git": {"full_name": "org/alpha",
                         "http_clone_url": "https://github.com/org/alpha.git"}},
    }


def test_empty_project_selector_keeps_policy():
    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        if kind == "Project":
            return _list([_tagged_project()])
        if kind == "Policy":
            return _list([
                {
                    "uuid": "pol-empty",
                    "meta": {"name": "All projects"},
                    "spec": {"policy_type": "POLICY_TYPE_ADMISSION",
                             "disable": False,
                             "project_selector": []},
                },
                {
                    "uuid": "pol-other",
                    "meta": {"name": "Other wave"},
                    "spec": {"policy_type": "POLICY_TYPE_ADMISSION",
                             "disable": False,
                             "project_selector": ["other-wave"]},
                },
                {
                    "uuid": "pol-off",
                    "meta": {"name": "Disabled"},
                    "spec": {"policy_type": "POLICY_TYPE_ADMISSION",
                             "disable": True,
                             "project_selector": []},
                },
            ])
        if kind == "ScanResult":
            return _list([])
        return _list([])

    snap = collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert [p.uuid for p in snap.policies] == ["pol-empty"]


def test_finding_maps_fields_and_package():
    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        if kind == "Project":
            return _list([_tagged_project()])
        if kind == "Policy":
            return _list([])
        if kind == "ScanResult":
            return _list([{
                "uuid": "s-warn",
                "meta": {"create_time": "2026-03-01T00:00:00Z", "parent_uuid": "p-alpha",
                         "tags": ["pr=1"]},
                "tenant_meta": {"namespace": "example-corp"},
                "context": {"tags": []},
                "spec": {"status": "ok", "warning_findings": ["f1", "f2"],
                         "blocking_findings": ["f3"]},
            }])
        if kind == "Finding":
            return _list([
                {
                    "uuid": "f1",
                    "meta": {"name": "cve", "description": "a finding"},
                    "tenant_meta": {"namespace": "example-corp"},
                    "spec": {
                        "level": "FINDING_LEVEL_CRITICAL",
                        "finding_categories": ["FINDING_CATEGORY_VULNERABILITY"],
                        "finding_tags": ["FINDING_TAGS_FIX_AVAILABLE"],
                        "target_dependency_package_name": "pkg-from-target",
                        "finding_metadata": {
                            "vulnerability": {"meta": {"name": "CVE-2026-0001"}},
                        },
                    },
                },
                {
                    "uuid": "f2",
                    "meta": {"name": "from-affected", "description": "pkg via affected"},
                    "tenant_meta": {"namespace": "example-corp"},
                    "spec": {
                        "level": "FINDING_LEVEL_HIGH",
                        "finding_categories": ["FINDING_CATEGORY_VULNERABILITY"],
                        "finding_tags": [],
                        "finding_metadata": {
                            "vulnerability": {
                                "meta": {"name": "CVE-2026-0002"},
                                "spec": {"affected": [{"package": {"name": "pkg-affected"}}]},
                            },
                        },
                    },
                },
                {
                    "uuid": "f3",
                    "meta": {"name": "sast-rule", "description": "sast"},
                    "tenant_meta": {"namespace": "example-corp"},
                    "spec": {
                        "level": "FINDING_LEVEL_MEDIUM",
                        "finding_categories": ["FINDING_CATEGORY_SAST"],
                        "finding_tags": [],
                    },
                },
            ])
        raise AssertionError(kind)

    snap = collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert set(snap.findings) == {"f1", "f2", "f3"}
    assert snap.findings["f1"].package == "pkg-from-target"
    assert snap.findings["f1"].severity == "CRITICAL"
    assert snap.findings["f1"].vuln_id == "CVE-2026-0001"
    assert snap.findings["f1"].violation_type == "Vulnerability"
    assert snap.findings["f1"].fix_available == "Yes"
    assert snap.findings["f2"].package == "pkg-affected"
    assert snap.findings["f3"].rule_id == "sast-rule"
    assert snap.findings["f3"].violation_type == "SAST"
    assert snap.projects["p-alpha"].base_url == "https://github.com/org/alpha"
    assert snap.meta.customer == "example-corp"
    assert snap.meta.project_count == 1


def test_scan_query_uses_ci_timeout_and_chunk_size():
    from collect import CHUNK

    timeouts = []

    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        timeouts.append((kind, timeout))
        if kind == "Project":
            return _list([_tagged_project()])
        if kind == "Policy":
            return _list([])
        if kind == "ScanResult":
            assert args[-2:] == ["-t", "300s"]
            assert "--sort-path" in args
            return _list([])
        return _list([])

    collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert CHUNK == 80
    assert ("ScanResult", 360) in timeouts


def test_collect_retries_then_succeeds():
    n = {"ScanResult": 0}

    def runner(args, namespace, timeout=120):
        kind = args[args.index("-r") + 1]
        if kind == "Project":
            return _list([_tagged_project()])
        if kind == "Policy":
            return _list([])
        if kind == "ScanResult":
            n["ScanResult"] += 1
            if n["ScanResult"] == 1:
                raise CollectError("boom", command=args)
            return _list([])
        return _list([])

    snap = collect("example-corp", ["rollout-wave-1"], 21, runner=runner)
    assert n["ScanResult"] == 2
    assert snap.scans == {}


def test_run_endorctl_raises_collect_error(monkeypatch):
    import collect as collect_mod

    def boom(*args, **kwargs):
        raise FileNotFoundError("endorctl")

    monkeypatch.setattr(collect_mod.subprocess, "run", boom)
    with pytest.raises(CollectError) as exc:
        collect_mod.run_endorctl(["api", "list", "-r", "Project"], "example-corp")
    assert exc.value.command == ["endorctl", "-n", "example-corp", "api", "list", "-r", "Project"]


def test_run_endorctl_raises_on_invalid_json(monkeypatch):
    import collect as collect_mod

    class Result:
        stdout = "not-json"

    monkeypatch.setattr(collect_mod.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(CollectError, match="invalid JSON"):
        collect_mod.run_endorctl(["api", "list"], "example-corp")
