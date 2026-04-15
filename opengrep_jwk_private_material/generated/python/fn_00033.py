import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"EW7Oi4xxKhO_","alg":"RS256","n":"wNJ-8gENS1wGK8ttwQXbFX4j6JYIhys2hQU3-CMIKmccoqWH","e":"AQAB"}
key_33 = {"kty":"RSA","kid":"EW7Oi4xxKhO_","alg":"RS256","n":"wNJ-8gENS1wGK8ttwQXbFX4j6JYIhys2hQU3-CMIKmccoqWH","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_33, algorithm='RS256').key)
