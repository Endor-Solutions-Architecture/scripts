import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"UZOgL71n3H-1","alg":"RS256","n":"FkaJDIx6wlssq7m1BfqD93SwZsZeeH3-fNhGvgiXKjUHg0ss","e":"AQAB"}
key_21 = {"kty":"RSA","kid":"UZOgL71n3H-1","alg":"RS256","n":"FkaJDIx6wlssq7m1BfqD93SwZsZeeH3-fNhGvgiXKjUHg0ss","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_21, algorithm='RS256').key)
