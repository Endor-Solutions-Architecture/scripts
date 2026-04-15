import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"Zv7FMdvQ9997","alg":"RS256","n":"TMTUcVeStlsna3tCGf94E3QkKXFkYb09ZylZCDiV1PkwmyGi","e":"AQAB"}
key_34 = {"kty":"RSA","kid":"Zv7FMdvQ9997","alg":"RS256","n":"TMTUcVeStlsna3tCGf94E3QkKXFkYb09ZylZCDiV1PkwmyGi","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_34, algorithm='RS256').key)
