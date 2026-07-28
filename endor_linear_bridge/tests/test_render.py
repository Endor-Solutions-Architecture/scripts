from dataclasses import dataclass
from datetime import datetime, timezone

from endor_linear_bridge.render import (
    NOTIFICATION_FOOTER_PREFIX,
    PARENT_CONTEXT_FOOTER_PREFIX,
    PARENT_PROJECT_FOOTER_PREFIX,
    PARENT_TEAM_FOOTER_PREFIX,
    notification_footer_query,
    parent_context_footer,
    parent_description,
    parent_footer_query,
    parent_resolution_comment,
    parent_team_footer,
    parent_title,
    reopen_comment,
    resolution_comment,
    sub_issue_description,
    sub_issue_title,
    update_comment,
)


@dataclass
class Row:
    uuid: str
    severity: str
    description: str
    finding_url: str | None = None


def row(n, severity="FINDING_LEVEL_HIGH"):
    return Row(
        uuid=f"f{n}",
        severity=severity,
        description=f"Finding {n}",
        finding_url=f"https://app.endorlabs.com/t/ns/findings/f{n}",
    )


DESC_KWARGS = dict(
    notification_uuid="notif-1",
    project_name="webapp",
    project_app_url="https://app.endorlabs.com/t/ns/projects/proj-1",
    policy_name="Critical vulns",
    policy_app_url="https://app.endorlabs.com/t/ns/policies/pol-1",
    max_findings=50,
)


def test_sub_issue_title_uses_dependency_name():
    assert sub_issue_title("npm://lodash") == "[Dep] npm://lodash"


def test_sub_issue_title_renames_the_no_deps_sentinel():
    assert (
        sub_issue_title("__ENDOR_FINDINGS_WITH_NO_DEPS__")
        == "Findings with no dependencies"
    )


def test_sub_issue_title_handles_empty_target():
    assert sub_issue_title("") == "Findings with no dependencies"


def test_parent_title_includes_project_and_ref():
    assert parent_title("webapp", "main") == "[Endor Labs] webapp — main"


def test_parent_title_omits_dash_when_ref_missing():
    assert parent_title("webapp", "") == "[Endor Labs] webapp"


def test_sub_issue_description_lists_every_finding():
    body = sub_issue_description(findings=[row(1), row(2)], **DESC_KWARGS)

    assert "Finding 1" in body
    assert "Finding 2" in body
    assert "https://app.endorlabs.com/t/ns/findings/f1" in body


def test_sub_issue_description_includes_recovery_footer():
    body = sub_issue_description(findings=[row(1)], **DESC_KWARGS)

    assert f"{NOTIFICATION_FOOTER_PREFIX} notif-1" in body


def test_sub_issue_description_includes_project_and_policy_links():
    body = sub_issue_description(findings=[row(1)], **DESC_KWARGS)

    assert "https://app.endorlabs.com/t/ns/projects/proj-1" in body
    assert "Critical vulns" in body


def test_sub_issue_description_orders_most_severe_first():
    findings = [row(1, "FINDING_LEVEL_LOW"), row(2, "FINDING_LEVEL_CRITICAL")]

    body = sub_issue_description(findings=findings, **DESC_KWARGS)

    assert body.index("Finding 2") < body.index("Finding 1")


def test_sub_issue_description_truncates_above_the_threshold():
    kwargs = dict(DESC_KWARGS, max_findings=2)
    findings = [row(n) for n in range(1, 6)]

    body = sub_issue_description(findings=findings, **kwargs)

    assert "and 3 more findings" in body
    assert "Finding 5" not in body


def test_sub_issue_description_does_not_truncate_at_the_threshold():
    kwargs = dict(DESC_KWARGS, max_findings=2)

    body = sub_issue_description(findings=[row(1), row(2)], **kwargs)

    assert "more findings" not in body


def test_sub_issue_description_handles_no_findings():
    body = sub_issue_description(findings=[], **DESC_KWARGS)

    assert f"{NOTIFICATION_FOOTER_PREFIX} notif-1" in body


def test_sub_issue_description_escapes_pipes_in_descriptions():
    """A raw pipe would break the Markdown table."""
    findings = [Row(uuid="f1", severity="FINDING_LEVEL_HIGH", description="a | b")]

    body = sub_issue_description(findings=findings, **DESC_KWARGS)

    assert r"a \| b" in body


def test_parent_description_includes_both_footers():
    body = parent_description(
        project_uuid="proj-1",
        context_id="main",
        team_key="plat",
        project_name="webapp",
        project_app_url="https://app.endorlabs.com/t/ns/projects/proj-1",
        policy_name="Critical vulns",
        policy_app_url="https://app.endorlabs.com/t/ns/policies/pol-1",
    )

    assert f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1" in body
    assert f"{PARENT_CONTEXT_FOOTER_PREFIX} main" in body


def test_parent_description_includes_the_team_footer():
    body = parent_description(
        project_uuid="proj-1",
        context_id="main",
        team_key="plat",
        project_name="webapp",
        project_app_url="https://app.endorlabs.com/t/ns/projects/proj-1",
        policy_name="Critical vulns",
        policy_app_url="https://app.endorlabs.com/t/ns/policies/pol-1",
    )

    assert f"{PARENT_TEAM_FOOTER_PREFIX} plat" in body


def test_parent_team_footer_distinguishes_teams():
    body = parent_description(
        project_uuid="proj-1",
        context_id="main",
        team_key="plat",
        project_name="webapp",
        project_app_url="",
        policy_name="",
        policy_app_url="",
    )

    assert parent_team_footer("plat") in body
    assert parent_team_footer("sec") not in body


def test_update_comment_reports_the_count_and_lists_findings():
    body = update_comment([row(1), row(2)])

    assert "2 new findings" in body
    assert "Finding 1" in body
    assert "Finding 2" in body


def test_update_comment_uses_singular_for_one_finding():
    assert "1 new finding" in update_comment([row(1)])


def test_resolution_comment_includes_the_timestamp():
    ts = datetime(2026, 7, 26, 12, 30, tzinfo=timezone.utc)

    body = resolution_comment(ts)

    assert "2026-07-26" in body
    assert "resolved" in body.lower()


def test_parent_resolution_comment_does_not_say_dependency():
    """Distinct from resolution_comment(): that wording is wrong on the parent,
    which closes because every sub-issue underneath it resolved, not because
    the parent itself is a dependency."""
    ts = datetime(2026, 7, 26, 12, 30, tzinfo=timezone.utc)

    body = parent_resolution_comment(ts)

    assert "2026-07-26" in body
    assert "resolved" in body.lower()
    assert "dependency" not in body.lower()


def test_reopen_comment_mentions_new_findings():
    assert "new findings" in reopen_comment().lower()


def test_notification_footer_query_is_searchable_text():
    assert notification_footer_query("notif-1") == f"{NOTIFICATION_FOOTER_PREFIX} notif-1"


def test_parent_footer_query_includes_project_uuid():
    assert parent_footer_query("proj-1") == f"{PARENT_PROJECT_FOOTER_PREFIX} proj-1"


def test_parent_context_footer_is_matchable_in_a_description():
    body = parent_description(
        project_uuid="proj-1",
        context_id="main",
        team_key="plat",
        project_name="webapp",
        project_app_url="",
        policy_name="",
        policy_app_url="",
    )

    assert parent_context_footer("main") in body
    assert parent_context_footer("release-2") not in body
