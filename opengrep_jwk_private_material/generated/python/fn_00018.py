import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"fHAHQUzQhc3l","alg":"RS256","n":"TNqdWZ0B29hWEz_Pj7tiAGe4AHc3IGTtE-Xjm82d9HuKvmlF","e":"AQAB"}
key_18 = {"kty":"RSA","kid":"fHAHQUzQhc3l","alg":"RS256","n":"TNqdWZ0B29hWEz_Pj7tiAGe4AHc3IGTtE-Xjm82d9HuKvmlF","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_18, algorithm='RS256').key)
