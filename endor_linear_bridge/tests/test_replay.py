import json

import httpx
import pytest
import respx

from endor_linear_bridge.auth import verify_bearer, verify_hmac
from endor_linear_bridge.tools.replay import build_headers, main

BODY = json.dumps({"event": "open"}).encode()


def test_build_headers_produces_a_verifiable_signature():
    headers = build_headers(BODY, bearer="tok", secret="sec")

    assert verify_hmac(BODY, headers["X-Endor-HMAC-Signature"], "sec") is True
    assert verify_bearer(headers["Authorization"], "tok") is True


def test_build_headers_sets_json_content_type():
    headers = build_headers(BODY, bearer="tok", secret="sec")

    assert headers["Content-Type"] == "application/json"


def test_signature_does_not_verify_with_the_wrong_secret():
    headers = build_headers(BODY, bearer="tok", secret="sec")

    assert verify_hmac(BODY, headers["X-Endor-HMAC-Signature"], "other") is False


def test_main_posts_the_payload_and_returns_zero(tmp_path):
    payload = tmp_path / "payload.json"
    payload.write_bytes(BODY)

    with respx.mock() as mock:
        route = mock.post("https://localhost:8443/hooks/plat").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        code = main(
            [
                "--url", "https://localhost:8443/hooks/plat",
                "--payload", str(payload),
                "--bearer", "tok",
                "--secret", "sec",
            ]
        )

    assert code == 0
    assert route.called
    request = route.calls[0].request
    assert request.content == BODY
    assert verify_hmac(
        BODY, request.headers["x-endor-hmac-signature"], "sec"
    ) is True


def test_main_returns_nonzero_on_non_200(tmp_path):
    payload = tmp_path / "payload.json"
    payload.write_bytes(BODY)

    with respx.mock() as mock:
        mock.post("https://localhost:8443/hooks/plat").mock(
            return_value=httpx.Response(503, json={"status": "retry later"})
        )

        code = main(
            [
                "--url", "https://localhost:8443/hooks/plat",
                "--payload", str(payload),
                "--bearer", "tok",
                "--secret", "sec",
            ]
        )

    assert code == 1


def test_main_reports_a_missing_payload_file(tmp_path, capsys):
    code = main(
        [
            "--url", "https://localhost:8443/hooks/plat",
            "--payload", str(tmp_path / "absent.json"),
            "--bearer", "tok",
            "--secret", "sec",
        ]
    )

    assert code == 2
    assert "absent.json" in capsys.readouterr().err
