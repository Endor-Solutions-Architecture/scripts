import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"rHSyK9sn9A29","alg":"RS256","n":"nJgPcLeIDZGnqG6qYH5QTMvlpRMAv1P6zdn6bgooImyllHjf","e":"AQAB"}
key_22 = {"kty":"RSA","kid":"rHSyK9sn9A29","alg":"RS256","n":"nJgPcLeIDZGnqG6qYH5QTMvlpRMAv1P6zdn6bgooImyllHjf","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_22, algorithm='RS256').key)
