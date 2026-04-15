import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"iGNCg3vOxv00","alg":"RS256","n":"Ir4uHTZwI14XIFEpZnf7QFqSd4omcnjME71AHIouyA3pkVz4","e":"AQAB"}
key_30 = {"kty":"RSA","kid":"iGNCg3vOxv00","alg":"RS256","n":"Ir4uHTZwI14XIFEpZnf7QFqSd4omcnjME71AHIouyA3pkVz4","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_30, algorithm='RS256').key)
