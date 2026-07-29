"""Inbound request authentication.

Endor signs the raw request body with HMAC-SHA256 and base64-encodes the
digest into X-Endor-HMAC-Signature (verified in monorepo
pkg/httphelper/httphelper.go:257-259). Both checks are constant-time.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac

SIGNATURE_HEADER = "X-Endor-HMAC-Signature"


def compute_signature(raw_body: bytes, secret: str) -> str:
    """Return base64(HMAC-SHA256(raw_body, secret)) -- what Endor sends."""
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_hmac(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify the signature over the raw bytes, before any JSON parsing."""
    if not signature_header:
        return False

    try:
        provided = base64.b64decode(signature_header, validate=True)
    except (binascii.Error, ValueError):
        return False

    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(provided, expected)


def verify_bearer(header_value: str | None, expected_token: str) -> bool:
    """Verify an 'Authorization: Bearer <token>' header.

    The Endor webhook plugin builds this header from a lowercase 'bearer' key
    (monorepo pkg/notificationplugins/handlers/webhook/webhook.go:412), so the
    scheme is compared case-insensitively while the token is exact.
    """
    if not header_value:
        return False

    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return False

    return hmac.compare_digest(token.strip().encode(), expected_token.encode())
