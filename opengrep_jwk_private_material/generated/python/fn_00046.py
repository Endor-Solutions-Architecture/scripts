import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"ikzCrO6FXrSQ","alg":"RS256","n":"dlpFNTYMvUTP_gvpKdS8nrWC-lkbGWXuepZH9cOxFWIFUbm9","e":"AQAB"}
key_46 = {"kty":"RSA","kid":"ikzCrO6FXrSQ","alg":"RS256","n":"dlpFNTYMvUTP_gvpKdS8nrWC-lkbGWXuepZH9cOxFWIFUbm9","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_46, algorithm='RS256').key)
