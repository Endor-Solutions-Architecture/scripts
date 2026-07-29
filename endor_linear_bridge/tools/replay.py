"""Replay a captured Endor webhook payload against a running bridge.

Recomputes the HMAC signature so a payload saved from a real scan can be
re-delivered as many times as needed while iterating on handler behavior.

    python -m endor_linear_bridge.tools.replay \
        --url https://localhost:8443/hooks/plat \
        --payload captured.json \
        --bearer "$BRIDGE_BEARER_TOKEN" \
        --secret "$ENDOR_HMAC_PLAT"

Note that redelivering the exact same bytes is a no-op by design: the
idempotency ledger keys on (notification uuid, event, payload hash). Edit a
field -- the notification uuid, or a finding -- to make the bridge treat it as a
new event.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import httpx

from endor_linear_bridge.auth import SIGNATURE_HEADER, compute_signature


def build_headers(body: bytes, *, bearer: str, secret: str) -> dict[str, str]:
    """The exact header set Endor's webhook plugin sends."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer}",
        SIGNATURE_HEADER: compute_signature(body, secret),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay a captured Endor webhook payload with a valid HMAC."
    )
    parser.add_argument("--url", required=True, help="e.g. https://localhost:8443/hooks/plat")
    parser.add_argument("--payload", required=True, help="path to a JSON payload file")
    parser.add_argument("--bearer", required=True, help="the bridge's inbound bearer token")
    parser.add_argument("--secret", required=True, help="the team's HMAC shared secret")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS verification (for a self-signed local certificate)",
    )
    args = parser.parse_args(argv)

    path = Path(args.payload)
    try:
        body = path.read_bytes()
    except OSError as exc:
        print(f"unable to read payload {path}: {exc}", file=sys.stderr)
        return 2

    response = httpx.post(
        args.url,
        content=body,
        headers=build_headers(body, bearer=args.bearer, secret=args.secret),
        verify=not args.insecure,
        timeout=60.0,
    )

    print(f"HTTP {response.status_code}: {response.text}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
