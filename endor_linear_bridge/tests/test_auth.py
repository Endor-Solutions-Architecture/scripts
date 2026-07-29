import base64
import hashlib
import hmac as hmac_mod

from endor_linear_bridge.auth import compute_signature, verify_bearer, verify_hmac

SECRET = "shared-secret"
BODY = b'{"event":"open"}'


def reference_signature(body: bytes, secret: str) -> str:
    digest = hmac_mod.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_compute_signature_matches_base64_hmac_sha256():
    assert compute_signature(BODY, SECRET) == reference_signature(BODY, SECRET)


def test_verify_hmac_accepts_valid_signature():
    assert verify_hmac(BODY, reference_signature(BODY, SECRET), SECRET) is True


def test_verify_hmac_rejects_tampered_body():
    signature = reference_signature(BODY, SECRET)
    assert verify_hmac(b'{"event":"resolve"}', signature, SECRET) is False


def test_verify_hmac_rejects_wrong_secret():
    signature = reference_signature(BODY, "other-secret")
    assert verify_hmac(BODY, signature, SECRET) is False


def test_verify_hmac_rejects_missing_header():
    assert verify_hmac(BODY, None, SECRET) is False


def test_verify_hmac_rejects_empty_header():
    assert verify_hmac(BODY, "", SECRET) is False


def test_verify_hmac_rejects_non_base64_header():
    assert verify_hmac(BODY, "not base64!!", SECRET) is False


def test_verify_hmac_rejects_hex_encoded_signature():
    """Endor sends base64, not hex -- a hex digest must not be accepted."""
    hex_digest = hmac_mod.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert verify_hmac(BODY, hex_digest, SECRET) is False


def test_verify_bearer_accepts_exact_token():
    assert verify_bearer("Bearer inbound-token", "inbound-token") is True


def test_verify_bearer_accepts_lowercase_scheme():
    """The Endor plugin builds the header from a lowercase 'bearer' key."""
    assert verify_bearer("bearer inbound-token", "inbound-token") is True


def test_verify_bearer_rejects_wrong_token():
    assert verify_bearer("Bearer nope", "inbound-token") is False


def test_verify_bearer_rejects_missing_header():
    assert verify_bearer(None, "inbound-token") is False


def test_verify_bearer_rejects_wrong_scheme():
    assert verify_bearer("Basic inbound-token", "inbound-token") is False


def test_verify_bearer_rejects_bare_token_without_scheme():
    assert verify_bearer("inbound-token", "inbound-token") is False
