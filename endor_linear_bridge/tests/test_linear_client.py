import httpx
import pytest
import respx

from endor_linear_bridge.linear_client import (
    LinearClient,
    LinearRequestError,
    LinearTransientError,
)

API_URL = "https://api.linear.app/graphql"


def build_client(**kwargs):
    kwargs.setdefault("sleep", _no_sleep)
    return LinearClient(api_key="lin_key", api_url=API_URL, **kwargs)


async def _no_sleep(_seconds):
    return None


def graphql_ok(data, headers=None):
    return httpx.Response(200, json={"data": data}, headers=headers or {})


async def test_execute_sends_api_key_without_bearer_prefix():
    async with respx.mock(assert_all_called=True) as mock:
        route = mock.post(API_URL).mock(return_value=graphql_ok({"ok": True}))

        await build_client().execute("query { ok }", {})

    assert route.calls[0].request.headers["authorization"] == "lin_key"


async def test_execute_posts_document_and_variables():
    async with respx.mock(assert_all_called=True) as mock:
        route = mock.post(API_URL).mock(return_value=graphql_ok({"ok": True}))

        await build_client().execute("query Q($a: String) { ok }", {"a": "b"})

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["query"] == "query Q($a: String) { ok }"
    assert body["variables"] == {"a": "b"}


async def test_execute_raises_on_graphql_errors_array():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=httpx.Response(
                200, json={"errors": [{"message": "Entity not found"}]}
            )
        )

        with pytest.raises(LinearRequestError, match="Entity not found"):
            await build_client().execute("query { ok }", {})


async def test_execute_raises_request_error_on_4xx():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(return_value=httpx.Response(400, text="bad request"))

        with pytest.raises(LinearRequestError):
            await build_client().execute("query { ok }", {})


async def test_execute_raises_request_error_on_401():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(return_value=httpx.Response(401, text="unauthorized"))

        with pytest.raises(LinearRequestError):
            await build_client().execute("query { ok }", {})


async def test_execute_retries_on_429_then_succeeds():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            side_effect=[
                httpx.Response(429, text="slow down"),
                graphql_ok({"ok": True}),
            ]
        )

        result = await build_client().execute("query { ok }", {})

    assert result == {"ok": True}
    assert route.call_count == 2


async def test_execute_retries_on_500_then_succeeds():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            side_effect=[httpx.Response(500), graphql_ok({"ok": True})]
        )

        await build_client().execute("query { ok }", {})

    assert route.call_count == 2


async def test_execute_raises_transient_after_exhausting_retries():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(return_value=httpx.Response(429))

        with pytest.raises(LinearTransientError):
            await build_client(max_attempts=3).execute("query { ok }", {})

    assert route.call_count == 3


async def test_execute_raises_transient_on_connect_error():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(side_effect=httpx.ConnectError("no route"))

        with pytest.raises(LinearTransientError):
            await build_client(max_attempts=2).execute("query { ok }", {})


async def test_execute_records_rate_limit_remaining():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok(
                {"ok": True}, headers={"X-RateLimit-Requests-Remaining": "1387"}
            )
        )
        client = build_client()

        await client.execute("query { ok }", {})

    assert client.last_rate_limit_remaining == 1387


async def test_teams_returns_nodes():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok(
                {"teams": {"nodes": [{"id": "t1", "key": "PLAT", "name": "Platform"}]}}
            )
        )

        teams = await build_client().teams()

    assert teams == [{"id": "t1", "key": "PLAT", "name": "Platform"}]


async def test_workflow_states_filters_by_team():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "workflowStates": {
                        "nodes": [{"id": "s1", "name": "Todo", "type": "unstarted"}]
                    }
                }
            )
        )

        states = await build_client().workflow_states("t1")

    import json

    assert json.loads(route.calls[0].request.content)["variables"]["teamId"] == "t1"
    assert states[0]["type"] == "unstarted"


async def test_issue_labels_returns_nodes():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok(
                {"issueLabels": {"nodes": [{"id": "l1", "name": "endorlabs"}]}}
            )
        )

        labels = await build_client().issue_labels("t1")

    assert labels == [{"id": "l1", "name": "endorlabs"}]


async def test_create_issue_label_returns_the_label():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "issueLabelCreate": {
                        "success": True,
                        "issueLabel": {"id": "l9", "name": "endor-critical"},
                    }
                }
            )
        )

        label = await build_client().create_issue_label("t1", "endor-critical")

    assert label == {"id": "l9", "name": "endor-critical"}


async def test_create_issue_sends_parent_and_returns_identifier():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "i1", "identifier": "PLAT-12"},
                    }
                }
            )
        )

        issue = await build_client().create_issue(
            team_id="t1",
            title="[Dep] lodash",
            description="body",
            parent_id="p1",
            state_id="s1",
            priority=1,
            label_ids=("l1",),
        )

    import json

    variables = json.loads(route.calls[0].request.content)["variables"]["input"]
    assert variables["teamId"] == "t1"
    assert variables["parentId"] == "p1"
    assert variables["stateId"] == "s1"
    assert variables["priority"] == 1
    assert variables["labelIds"] == ["l1"]
    assert issue == {"id": "i1", "identifier": "PLAT-12"}


async def test_create_issue_omits_optional_fields_when_not_given():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "i1", "identifier": "PLAT-12"},
                    }
                }
            )
        )

        await build_client().create_issue(
            team_id="t1", title="t", description="d"
        )

    import json

    variables = json.loads(route.calls[0].request.content)["variables"]["input"]
    assert "parentId" not in variables
    assert "priority" not in variables
    assert "labelIds" not in variables


async def test_create_issue_raises_when_success_is_false():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok({"issueCreate": {"success": False, "issue": None}})
        )

        with pytest.raises(LinearRequestError, match="issueCreate"):
            await build_client().create_issue(
                team_id="t1", title="t", description="d"
            )


async def test_update_issue_sends_only_provided_fields():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "issueUpdate": {
                        "success": True,
                        "issue": {"id": "i1", "identifier": "PLAT-12"},
                    }
                }
            )
        )

        await build_client().update_issue("i1", state_id="s-done")

    import json

    body = json.loads(route.calls[0].request.content)["variables"]
    assert body["id"] == "i1"
    assert body["input"] == {"stateId": "s-done"}


async def test_update_issue_sends_empty_label_list_when_explicitly_empty():
    """label_ids=() must clear labels, so it cannot be treated as 'not provided'."""
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "issueUpdate": {
                        "success": True,
                        "issue": {"id": "i1", "identifier": "PLAT-12"},
                    }
                }
            )
        )

        await build_client().update_issue("i1", label_ids=())

    import json

    body = json.loads(route.calls[0].request.content)["variables"]
    assert body["input"] == {"labelIds": []}


async def test_update_issue_raises_when_success_is_false():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok({"issueUpdate": {"success": False, "issue": None}})
        )

        with pytest.raises(LinearRequestError, match="issueUpdate"):
            await build_client().update_issue("i1", state_id="s1")


async def test_create_comment_posts_the_body():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok({"commentCreate": {"success": True}})
        )

        await build_client().create_comment("i1", "hello")

    import json

    variables = json.loads(route.calls[0].request.content)["variables"]["input"]
    assert variables == {"issueId": "i1", "body": "hello"}


async def test_create_comment_raises_when_success_is_false():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(
            return_value=graphql_ok({"commentCreate": {"success": False}})
        )

        with pytest.raises(LinearRequestError, match="commentCreate"):
            await build_client().create_comment("i1", "hello")


async def test_search_issues_returns_nodes():
    async with respx.mock() as mock:
        route = mock.post(API_URL).mock(
            return_value=graphql_ok(
                {
                    "searchIssues": {
                        "nodes": [
                            {
                                "id": "i1",
                                "identifier": "PLAT-12",
                                "description": "Endor-notification-uuid: notif-1",
                            }
                        ]
                    }
                }
            )
        )

        results = await build_client().search_issues("Endor-notification-uuid: notif-1")

    import json

    assert (
        json.loads(route.calls[0].request.content)["variables"]["term"]
        == "Endor-notification-uuid: notif-1"
    )
    assert results[0]["identifier"] == "PLAT-12"


async def test_search_issues_returns_empty_list_when_no_matches():
    async with respx.mock() as mock:
        mock.post(API_URL).mock(return_value=graphql_ok({"searchIssues": {"nodes": []}}))

        assert await build_client().search_issues("nothing") == []
