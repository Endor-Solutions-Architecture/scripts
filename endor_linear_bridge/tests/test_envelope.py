import json

import pytest

from endor_linear_bridge.envelope import (
    NO_DEPS_SENTINEL,
    EnvelopeError,
    parse_envelope,
)

FULL = {
    "event": "open",
    "notification": {
        "uuid": "notif-1",
        "project_uuid": "proj-1",
        "project_name": "webapp",
        "project_app_url": "https://app.endorlabs.com/t/ns/projects/proj-1",
        "ref_name": "main",
        "context_id": "main",
        "policy_uuid": "pol-1",
        "policy_name": "Critical vulns",
        "policy_app_url": "https://app.endorlabs.com/t/ns/policies/pol-1",
        "aggregation": {
            "type": "AGGREGATION_TYPE_DEPENDENCY_ACROSS_PKG_VERSIONS",
            "target_name": "npm://lodash",
            "pkg_version_uuid": "",
        },
    },
    "diff": {"new_finding_uuids": ["f1"], "resolved_finding_uuids": []},
    "findings": [
        {
            "uuid": "f1",
            "description": "Prototype pollution",
            "severity": "FINDING_LEVEL_CRITICAL",
            "dependency": "lodash@4.17.4",
            "package": "webapp@1.5.0",
            "finding_url": "https://app.endorlabs.com/t/ns/findings/f1",
        }
    ],
}


def body(payload):
    return json.dumps(payload).encode()


def test_parse_envelope_reads_all_fields():
    env = parse_envelope(body(FULL))

    assert env.event == "open"
    assert env.notification.uuid == "notif-1"
    assert env.notification.project_uuid == "proj-1"
    assert env.notification.project_name == "webapp"
    assert env.notification.ref_name == "main"
    assert env.notification.context_id == "main"
    assert env.notification.policy_name == "Critical vulns"
    assert env.notification.aggregation.target_name == "npm://lodash"
    assert env.diff.new_finding_uuids == ["f1"]
    assert len(env.findings) == 1
    assert env.findings[0].severity == "FINDING_LEVEL_CRITICAL"
    assert env.findings[0].dependency == "lodash@4.17.4"


def test_parse_envelope_accepts_empty_aggregation_block():
    """Go templates emit {} when AggregationDetails is nil."""
    payload = json.loads(json.dumps(FULL))
    payload["notification"]["aggregation"] = {}

    env = parse_envelope(body(payload))

    assert env.notification.aggregation.type == ""
    assert env.notification.aggregation.target_name == ""
    assert env.notification.aggregation.pkg_version_uuid == ""


def test_parse_envelope_accepts_empty_diff_block():
    """Go templates emit {} when Diff is nil."""
    payload = json.loads(json.dumps(FULL))
    payload["diff"] = {}

    env = parse_envelope(body(payload))

    assert env.diff.new_finding_uuids == []
    assert env.diff.resolved_finding_uuids == []


def test_parse_envelope_accepts_resolve_without_findings():
    """The resolve template omits the findings array entirely."""
    payload = {
        "event": "resolve",
        "notification": {"uuid": "notif-1", "project_uuid": "proj-1"},
        "diff": {},
    }

    env = parse_envelope(body(payload))

    assert env.event == "resolve"
    assert env.findings == []


def test_parse_envelope_accepts_no_deps_sentinel():
    payload = json.loads(json.dumps(FULL))
    payload["notification"]["aggregation"]["target_name"] = NO_DEPS_SENTINEL

    env = parse_envelope(body(payload))

    assert env.notification.aggregation.target_name == NO_DEPS_SENTINEL


def test_parse_envelope_defaults_optional_finding_fields():
    payload = json.loads(json.dumps(FULL))
    payload["findings"] = [{"uuid": "f9"}]

    env = parse_envelope(body(payload))
    finding = env.findings[0]

    assert finding.uuid == "f9"
    assert finding.description == ""
    assert finding.severity == ""
    assert finding.dependency is None
    assert finding.finding_url is None


def test_parse_envelope_rejects_invalid_json():
    with pytest.raises(EnvelopeError, match="not valid JSON"):
        parse_envelope(b"{not json")


def test_parse_envelope_rejects_unknown_event():
    payload = json.loads(json.dumps(FULL))
    payload["event"] = "deleted"

    with pytest.raises(EnvelopeError):
        parse_envelope(body(payload))


def test_parse_envelope_rejects_missing_notification_uuid():
    payload = json.loads(json.dumps(FULL))
    del payload["notification"]["uuid"]

    with pytest.raises(EnvelopeError, match="uuid"):
        parse_envelope(body(payload))


def test_parse_envelope_rejects_missing_project_uuid():
    payload = json.loads(json.dumps(FULL))
    del payload["notification"]["project_uuid"]

    with pytest.raises(EnvelopeError, match="project_uuid"):
        parse_envelope(body(payload))


def test_parse_envelope_rejects_empty_body():
    with pytest.raises(EnvelopeError):
        parse_envelope(b"")
