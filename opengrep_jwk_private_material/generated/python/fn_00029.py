import jwt

# JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
key_29 = {"kty":"oct","kid":"missing-k","alg":"HS256"}
print(jwt.PyJWK.from_dict(key_29, algorithm='HS256').key)
