import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"uo7pz_ZjGS62","alg":"RS256","n":"Rm3eW28SMFxqjqW9WgUwSD8zc26wUQ-S6m95eg21X8LR2BVC","e":"AQAB"}
key_40 = {"kty":"RSA","kid":"uo7pz_ZjGS62","alg":"RS256","n":"Rm3eW28SMFxqjqW9WgUwSD8zc26wUQ-S6m95eg21X8LR2BVC","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_40, algorithm='RS256').key)
