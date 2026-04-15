import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"oMmXqSoL_0bS","alg":"RS256","n":"3LzMgimnt_8WnXBWZv8ODEV8DIbM42BXWZeR9D7iJ8JUmPpN","e":"AQAB"}
key_24 = {"kty":"RSA","kid":"oMmXqSoL_0bS","alg":"RS256","n":"3LzMgimnt_8WnXBWZv8ODEV8DIbM42BXWZeR9D7iJ8JUmPpN","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_24, algorithm='RS256').key)
