import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"870s5K8Pu15w","alg":"RS256","n":"pRdUxBHN2x-3SrTNxrj5S0ANUuCyJKeO7y_0WYQIfE2zId_X","e":"AQAB"}
key_12 = {"kty":"RSA","kid":"870s5K8Pu15w","alg":"RS256","n":"pRdUxBHN2x-3SrTNxrj5S0ANUuCyJKeO7y_0WYQIfE2zId_X","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_12, algorithm='RS256').key)
