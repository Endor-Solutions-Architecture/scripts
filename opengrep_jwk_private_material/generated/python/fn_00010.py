import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"qXeoVqkpo31O","alg":"RS256","n":"hA27SqrxlvEpAGagDQoTogeJXOBSlh4kR12-4AgSnMA9BG4J","e":"AQAB"}
key_10 = {"kty":"RSA","kid":"qXeoVqkpo31O","alg":"RS256","n":"hA27SqrxlvEpAGagDQoTogeJXOBSlh4kR12-4AgSnMA9BG4J","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_10, algorithm='RS256').key)
