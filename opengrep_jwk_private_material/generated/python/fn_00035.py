import jwt

# JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
key_35 = {"kty":"oct","kid":"missing-k","alg":"HS256"}
print(jwt.PyJWK.from_dict(key_35, algorithm='HS256').key)
