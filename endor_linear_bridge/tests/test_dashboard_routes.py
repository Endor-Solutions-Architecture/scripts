"""/dashboard: the read-only Mission Control UI.

Served with no authentication (deployment restricts it at ingress, like
/metrics), so none of these requests send a bearer token or signature.
"""

import pytest
from fastapi.testclient import TestClient

from endor_linear_bridge.app import create_app
from endor_linear_bridge.handlers import HandlerDeps
from endor_linear_bridge.tests.linear_fake import FakeLinearClient
from endor_linear_bridge.tests.test_app import post
from endor_linear_bridge.tests.test_handlers_open import (
    CONFIG,
    RUNTIME,
    envelope_body,
)


@pytest.fixture
def client(session_factory):
    deps = HandlerDeps(
        session_factory=session_factory,
        client=FakeLinearClient(),
        runtimes={"plat": RUNTIME},
        config=CONFIG,
    )
    with TestClient(create_app(CONFIG, deps=deps)) as test_client:
        test_client.deps = deps
        yield test_client


@pytest.mark.parametrize(
    "path,marker",
    [
        ("/dashboard", "Mission control"),
        ("/dashboard/deliveries", "Delivery log"),
        ("/dashboard/teams", "Workflow states resolved"),
        ("/dashboard/config", "Failure semantics"),
    ],
)
def test_pages_render_without_auth(client, path, marker):
    response = client.get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert marker in response.text


def test_overview_reflects_processed_deliveries(client):
    post(client, envelope_body())

    page = client.get("/dashboard").text
    assert "plat" in page
    assert "Operational" in page


def test_overview_renders_update_counts_not_dict_methods(client):
    # Jinja resolves dict.update to the dict METHOD, not the key -- the
    # template must use subscript access for the 'update' event count.
    post(client, envelope_body())
    post(client, envelope_body(event="update", uuid="notif-1"))

    page = client.get("/dashboard").text
    assert "built-in method" not in page
    assert "1 update" in page


def test_overview_names_failures_instead_of_boilerplate(client):
    post(client, envelope_body(), secret="wrong")

    page = client.get("/dashboard").text
    assert "Operational" not in page
    assert "rejected" in page


def test_deliveries_page_lists_the_delivery_with_its_linear_id(client):
    post(client, envelope_body())

    page = client.get("/dashboard/deliveries").text
    assert "npm://lodash" in page
    assert "PLAT-" in page


def test_deliveries_page_search_filters_rows(client):
    post(client, envelope_body())
    post(client, envelope_body(uuid="notif-2", target="pypi://requests"))

    page = client.get("/dashboard/deliveries", params={"q": "lodash"}).text
    assert "npm://lodash" in page
    assert "pypi://requests" not in page


def test_deliveries_page_event_filter(client):
    post(client, envelope_body())
    post(client, envelope_body(event="update", uuid="notif-2", target="pypi://requests"))

    page = client.get("/dashboard/deliveries", params={"filter": "update"}).text
    assert "pypi://requests" in page
    assert "npm://lodash" not in page


def test_invalid_window_falls_back_to_default(client):
    response = client.get("/dashboard", params={"window": "bogus"})

    assert response.status_code == 200


def test_teams_page_shows_route_and_resolved_state_ids(client):
    page = client.get("/dashboard/teams").text

    assert "/hooks/plat" in page
    assert "s-todo" in page  # open state id from the test runtime


def test_config_page_never_shows_secrets(client):
    page = client.get("/dashboard/config").text

    assert CONFIG.inbound_bearer_token not in page
    assert CONFIG.linear_api_key not in page
    assert "secret" not in page.lower() or "never shown" in page.lower()


def test_static_assets_are_served(client):
    response = client.get("/dashboard/static/dashboard.css")

    assert response.status_code == 200
