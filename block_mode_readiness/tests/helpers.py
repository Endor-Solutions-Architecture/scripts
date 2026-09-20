from __future__ import annotations

from snapshot import Finding, Policy, Project, Scan, Snapshot, SnapshotMeta


def make_project(**kwargs) -> Project:
    data = dict(
        uuid="p-alpha",
        full_name="org/alpha",
        base_url="https://github.com/org/alpha",
        namespace="example-corp",
        tags=["rollout-wave-1"],
    )
    data.update(kwargs)
    return Project(**data)


def make_finding(**kwargs) -> Finding:
    data = dict(
        uuid="f1",
        violation_type="Vulnerability",
        severity="CRITICAL",
        description="CVE-2026-0001 in pkg",
        vuln_id="CVE-2026-0001",
        rule_id="",
        package="pkg",
        reachable="Reachable",
        fix_available="Yes",
        namespace="example-corp",
    )
    data.update(kwargs)
    return Finding(**data)


def make_scan(**kwargs) -> Scan:
    data = dict(
        uuid="s1",
        create_time="2026-03-01T12:00:00Z",
        project_uuid="p-alpha",
        pr_number="10",
        outcome="warn",
        warning_finding_ids=["f1"],
        blocking_finding_ids=[],
        status="STATUS_SUCCESS",
        namespace="example-corp",
        policy_name="",
    )
    data.update(kwargs)
    return Scan(**data)


def make_meta(**kwargs) -> SnapshotMeta:
    data = dict(
        namespace="example-corp",
        project_tags=["rollout-wave-1"],
        days=21,
        mark_dates={"sast": "2026-03-10"},
        customer="Example Corp",
        decision_date="2026-06-01",
        generated_at="2026-03-21T18:00:00Z",
        ci_runs_dropped_no_pr=0,
        project_count=2,
    )
    data.update(kwargs)
    return SnapshotMeta(**data)


def make_snapshot(**kwargs) -> Snapshot:
    projects = {
        "p-alpha": make_project(),
        "p-beta": make_project(uuid="p-beta", full_name="org/beta",
                               base_url="https://github.com/org/beta"),
    }
    findings = {"f1": make_finding()}
    scans = {"s1": make_scan()}
    data = dict(
        meta=make_meta(),
        projects=projects,
        scans=scans,
        findings=findings,
        policies=[Policy(uuid="pol1", name="Warn on critical",
                         selector_tags=["rollout-wave-1"], disabled=False)],
    )
    data.update(kwargs)
    return Snapshot(**data)


def full_sample_snapshot() -> Snapshot:
    findings = {
        "f-vuln": make_finding(
            uuid="f-vuln",
            violation_type="Vulnerability",
            severity="CRITICAL",
        ),
        "f-sast": make_finding(
            uuid="f-sast",
            violation_type="SAST",
            severity="HIGH",
        ),
        "f-sec": make_finding(
            uuid="f-sec",
            violation_type="Secrets",
            severity="HIGH",
        ),
        "f-ai": make_finding(
            uuid="f-ai",
            violation_type="AI SAST",
            severity="MEDIUM",
        ),
        "f-vuln2": make_finding(
            uuid="f-vuln2",
            violation_type="Vulnerability",
            severity="HIGH",
        ),
        "f-vuln3": make_finding(
            uuid="f-vuln3",
            violation_type="Vulnerability",
            severity="HIGH",
        ),
    }
    scans = {
        "s1": make_scan(
            uuid="s1",
            create_time="2026-03-01T12:00:00Z",
            pr_number="10",
            outcome="warn",
            warning_finding_ids=["f-vuln", "f-sast"],
        ),
        "s2": make_scan(
            uuid="s2",
            create_time="2026-03-05T12:00:00Z",
            pr_number="10",
            outcome="warn",
            warning_finding_ids=["f-vuln"],
        ),
        "s3": make_scan(
            uuid="s3",
            create_time="2026-03-02T12:00:00Z",
            pr_number="11",
            outcome="warn",
            warning_finding_ids=["f-sec"],
        ),
        "s4": make_scan(
            uuid="s4",
            create_time="2026-03-06T12:00:00Z",
            pr_number="11",
            outcome="warn",
            warning_finding_ids=["f-sec"],
        ),
        "s5": make_scan(
            uuid="s5",
            create_time="2026-03-20T12:00:00Z",
            pr_number="12",
            outcome="warn",
            warning_finding_ids=["f-ai"],
        ),
        "s6": make_scan(
            uuid="s6",
            create_time="2026-03-03T12:00:00Z",
            pr_number="13",
            outcome="warn",
            warning_finding_ids=["f-vuln2", "f-vuln3"],
        ),
        "s7": make_scan(
            uuid="s7",
            create_time="2026-03-08T12:00:00Z",
            pr_number="13",
            outcome="clean",
            warning_finding_ids=[],
        ),
        "s8": make_scan(
            uuid="s8",
            create_time="2026-03-04T12:00:00Z",
            pr_number="14",
            outcome="clean",
            warning_finding_ids=[],
        ),
    }
    return make_snapshot(findings=findings, scans=scans)
