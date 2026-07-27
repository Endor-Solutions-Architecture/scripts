"""Guards against drift between the Go templates and the Python parser.

Go templates cannot be executed here, so these tests assert that
representative rendered output -- including the degenerate shapes the `with`
guards produce for nil protobuf fields -- parses into a usable Envelope.
"""

import json
from pathlib import Path

import pytest

from endor_linear_bridge.envelope import NO_DEPS_SENTINEL, parse_envelope

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATES = Path(__file__).parent.parent / "templates"


def fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


@pytest.mark.parametrize(
    "name", ["rendered_open.json", "rendered_update.json", "rendered_resolve.json",
             "rendered_minimal.json"]
)
def test_every_fixture_parses(name):
    parse_envelope(fixture_bytes(name))


@pytest.mark.parametrize(
    "name", ["rendered_open.json", "rendered_update.json", "rendered_resolve.json",
             "rendered_minimal.json"]
)
def test_every_fixture_is_valid_json(name):
    json.loads(fixture_bytes(name))


def test_open_fixture_carries_the_full_finding_set():
    env = parse_envelope(fixture_bytes("rendered_open.json"))

    assert env.event == "open"
    assert len(env.findings) == 2
    assert env.notification.aggregation.target_name == "npm://lodash"


def test_update_fixture_carries_only_new_findings():
    env = parse_envelope(fixture_bytes("rendered_update.json"))

    assert env.event == "update"
    assert [f.uuid for f in env.findings] == env.diff.new_finding_uuids


def test_resolve_fixture_has_no_findings():
    env = parse_envelope(fixture_bytes("rendered_resolve.json"))

    assert env.event == "resolve"
    assert env.findings == []
    assert env.notification.uuid


def test_minimal_fixture_tolerates_empty_blocks():
    env = parse_envelope(fixture_bytes("rendered_minimal.json"))

    assert env.notification.aggregation.type == ""
    assert env.notification.aggregation.target_name == ""
    assert env.diff.new_finding_uuids == []
    assert env.notification.context_id == ""
    assert env.findings[0].dependency is None


@pytest.mark.parametrize("name", ["open.tmpl", "update.tmpl", "resolve.tmpl"])
def test_template_files_exist_and_are_not_empty(name):
    content = (TEMPLATES / name).read_text()

    assert content.strip()


@pytest.mark.parametrize("name", ["open.tmpl", "update.tmpl", "resolve.tmpl"])
def test_templates_guard_optional_fields_with_with(name):
    """Direct .Value on a nil wrapper is a template execution error."""
    content = (TEMPLATES / name).read_text()

    assert "{{ with .RawNotification.Spec.AggregationDetails }}" in content or (
        "{{- with .RawNotification.Spec.AggregationDetails }}" in content
    )
    assert ".RawNotification.Spec.AggregationDetails.PkgVersionUuid.Value" not in content


@pytest.mark.parametrize("name", ["open.tmpl", "update.tmpl", "resolve.tmpl"])
def test_templates_declare_the_matching_event(name):
    content = (TEMPLATES / name).read_text()
    expected = name.removesuffix(".tmpl")

    assert f'"event": "{expected}"' in content


def test_resolve_template_omits_the_findings_array():
    content = (TEMPLATES / "resolve.tmpl").read_text()

    assert '"findings"' not in content


@pytest.mark.parametrize("name", ["open.tmpl", "update.tmpl"])
def test_finding_templates_json_escape_free_text(name):
    content = (TEMPLATES / name).read_text()

    assert "jsonEscape" in content
    assert '"findings"' in content


def test_no_deps_sentinel_is_recognized_by_the_parser():
    payload = json.loads(fixture_bytes("rendered_minimal.json"))
    payload["notification"]["aggregation"] = {"target_name": NO_DEPS_SENTINEL}

    env = parse_envelope(json.dumps(payload).encode())

    assert env.notification.aggregation.target_name == NO_DEPS_SENTINEL
