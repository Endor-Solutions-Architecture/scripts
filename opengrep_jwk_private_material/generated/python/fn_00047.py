import jwt

# JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
key_47 = {"kty":"oct","kid":"missing-k","alg":"HS256"}
print(jwt.PyJWK.from_dict(key_47, algorithm='HS256').key)
