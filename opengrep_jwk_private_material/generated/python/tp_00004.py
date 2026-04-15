import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"1omcQ8m2C5r0","alg":"RS256","n":"ws8I_hM8rsGc51NMKPb8y5pfpkLo9cDAQMtZithzSWhBd2nC","e":"AQAB","d":"L_3fs0qd"}
key_4 = {"kty":"RSA","kid":"1omcQ8m2C5r0","alg":"RS256","n":"ws8I_hM8rsGc51NMKPb8y5pfpkLo9cDAQMtZithzSWhBd2nC","e":"AQAB","d":"L_3fs0qd"}
print(jwt.PyJWK.from_dict(key_4, algorithm='RS256').key)
