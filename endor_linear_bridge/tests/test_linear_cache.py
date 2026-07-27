import httpx
import pytest
import respx

from endor_linear_bridge.config import Config, TeamConfig
from endor_linear_bridge.linear_cache import (
    StartupError,
    build_team_runtimes,
    pick_state,
)
from endor_linear_bridge.linear_client import LinearClient

API_URL = "https://api.linear.app/graphql"

STATES = [
    {"id": "s-triage", "name": "Triage", "type": "triage"},
    {"id": "s-todo", "name": "Todo", "type": "unstarted"},
    {"id": "s-doing", "name": "In Progress", "type": "started"},
    {"id": "s-done", "name": "Done", "type": "completed"},
    {"id": "s-cancel", "name": "Canceled", "type": "canceled"},
]


def team_config(**overrides):
    defaults = dict(
        key="plat",
        linear_team_key="PLAT",
        hmac_secret="secret",
        open_state=None,
        close_state=None,
        reopen_state=None,
        labels=(),
        priority_from_severity=True,
        severity_labels=True,
        severity_label_prefix="endor-",
    )
    defaults.update(overrides)
    return TeamConfig(**defaults)


def config_with(team):
    return Config(
        linear_api_key="lin_key",
        linear_api_url=API_URL,
        inbound_bearer_token="token",
        database_url="sqlite:///:memory:",
        max_findings_per_issue=50,
        teams={team.key: team},
    )


async def _no_sleep(_seconds):
    return None


def client():
    return LinearClient(api_key="lin_key", api_url=API_URL, sleep=_no_sleep)


def test_pick_state_defaults_to_first_matching_type():
    chosen = pick_state(
        STATES, override_name=None, wanted_type="completed", team_key="plat",
        purpose="close_state",
    )
    assert chosen == "s-done"


def test_pick_state_honors_a_name_override():
    chosen = pick_state(
        STATES, override_name="Triage", wanted_type="unstarted", team_key="plat",
        purpose="open_state",
    )
    assert chosen == "s-triage"


def test_pick_state_name_override_is_case_insensitive():
    chosen = pick_state(
        STATES, override_name="done", wanted_type="unstarted", team_key="plat",
        purpose="open_state",
    )
    assert chosen == "s-done"


def test_pick_state_raises_when_override_name_absent():
    with pytest.raises(StartupError, match="Nonexistent"):
        pick_state(
            STATES, override_name="Nonexistent", wanted_type="unstarted",
            team_key="plat", purpose="open_state",
        )


def test_pick_state_raises_when_no_state_of_type_exists():
    states = [{"id": "s1", "name": "Todo", "type": "unstarted"}]
    with pytest.raises(StartupError, match="completed"):
        pick_state(
            states, override_name=None, wanted_type="completed", team_key="plat",
            purpose="close_state",
        )


def graphql(data):
    return httpx.Response(200, json={"data": data})


def mock_startup(mock, *, teams, states, labels, created_labels=None):
    """Route each GraphQL operation by the operation name in the request body."""
    created = list(created_labels or [])

    def responder(request):
        import json

        body = json.loads(request.content)
        document = body["query"]
        if "query Teams" in document:
            return graphql({"teams": {"nodes": teams}})
        if "query States" in document:
            return graphql({"workflowStates": {"nodes": states}})
        if "query Labels" in document:
            return graphql({"issueLabels": {"nodes": labels}})
        if "mutation LabelCreate" in document:
            name = body["variables"]["input"]["name"]
            label = {"id": f"new-{name}", "name": name}
            created.append(label)
            return graphql(
                {"issueLabelCreate": {"success": True, "issueLabel": label}}
            )
        raise AssertionError(f"unexpected document: {document}")

    mock.post(API_URL).mock(side_effect=responder)
    return created


async def test_build_team_runtimes_resolves_team_and_states():
    team = team_config()
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    runtime = runtimes["plat"]
    assert runtime.linear_team_id == "t1"
    assert runtime.open_state_id == "s-todo"
    assert runtime.close_state_id == "s-done"
    assert runtime.reopen_state_id == "s-todo"


async def test_build_team_runtimes_honors_state_overrides():
    team = team_config(open_state="Triage", close_state="Canceled", reopen_state="Done")
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    runtime = runtimes["plat"]
    assert runtime.open_state_id == "s-triage"
    assert runtime.close_state_id == "s-cancel"
    assert runtime.reopen_state_id == "s-done"


async def test_build_team_runtimes_raises_for_unknown_team_key():
    team = team_config(linear_team_key="NOPE")
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        with pytest.raises(StartupError, match="NOPE"):
            await build_team_runtimes(client(), config_with(team))


async def test_build_team_runtimes_reuses_existing_labels():
    team = team_config(labels=("endorlabs",))
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[{"id": "l-existing", "name": "endorlabs"}],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    assert runtimes["plat"].base_label_ids == ("l-existing",)


async def test_build_team_runtimes_creates_missing_labels():
    team = team_config(labels=("endorlabs",), severity_labels=False)
    async with respx.mock() as mock:
        created = mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    assert runtimes["plat"].base_label_ids == ("new-endorlabs",)
    assert [label["name"] for label in created] == ["endorlabs"]


async def test_build_team_runtimes_creates_severity_labels():
    team = team_config()
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    severity_labels = runtimes["plat"].severity_label_ids
    assert severity_labels["critical"] == "new-endor-critical"
    assert severity_labels["high"] == "new-endor-high"
    assert severity_labels["medium"] == "new-endor-medium"
    assert severity_labels["low"] == "new-endor-low"


async def test_build_team_runtimes_skips_severity_labels_when_disabled():
    team = team_config(severity_labels=False)
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    assert runtimes["plat"].severity_label_ids == {}


async def test_build_team_runtimes_uses_the_configured_prefix():
    team = team_config(severity_label_prefix="sev-")
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtimes = await build_team_runtimes(client(), config_with(team))

    assert runtimes["plat"].severity_label_ids["critical"] == "new-sev-critical"


async def test_label_ids_for_combines_base_and_severity_labels():
    team = team_config(labels=("endorlabs",))
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[{"id": "l-existing", "name": "endorlabs"}],
        )

        runtime = (await build_team_runtimes(client(), config_with(team)))["plat"]

    assert runtime.label_ids_for("FINDING_LEVEL_CRITICAL") == (
        "l-existing",
        "new-endor-critical",
    )


async def test_label_ids_for_omits_severity_label_when_unrecognized():
    team = team_config(labels=("endorlabs",))
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[{"id": "l-existing", "name": "endorlabs"}],
        )

        runtime = (await build_team_runtimes(client(), config_with(team)))["plat"]

    assert runtime.label_ids_for("") == ("l-existing",)


async def test_priority_for_severity_maps_when_enabled():
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtime = (
            await build_team_runtimes(client(), config_with(team_config()))
        )["plat"]

    assert runtime.priority_for_severity("FINDING_LEVEL_CRITICAL") == 1


async def test_priority_for_severity_is_zero_when_disabled():
    team = team_config(priority_from_severity=False)
    async with respx.mock() as mock:
        mock_startup(
            mock,
            teams=[{"id": "t1", "key": "PLAT", "name": "Platform"}],
            states=STATES,
            labels=[],
        )

        runtime = (await build_team_runtimes(client(), config_with(team)))["plat"]

    assert runtime.priority_for_severity("FINDING_LEVEL_CRITICAL") == 0
