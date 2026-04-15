import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"GfHf-pGz9Qpt","alg":"RS256","n":"TTN9ubukCZqgjZSgchtRTwPqGxg7iR6WZYzIwe1DIPXmrJfj","e":"AQAB"}
key_39 = {"kty":"RSA","kid":"GfHf-pGz9Qpt","alg":"RS256","n":"TTN9ubukCZqgjZSgchtRTwPqGxg7iR6WZYzIwe1DIPXmrJfj","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_39, algorithm='RS256').key)
