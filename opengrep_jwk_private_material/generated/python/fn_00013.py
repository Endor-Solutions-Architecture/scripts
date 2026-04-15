import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"miKBpKIRnQlU","alg":"RS256","n":"HJ1BHO6Fo_YeL4NrVb2oOkcfZ8X2DUP8BWo4gIFEGw2ATynP","e":"AQAB"}
key_13 = {"kty":"RSA","kid":"miKBpKIRnQlU","alg":"RS256","n":"HJ1BHO6Fo_YeL4NrVb2oOkcfZ8X2DUP8BWo4gIFEGw2ATynP","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_13, algorithm='RS256').key)
