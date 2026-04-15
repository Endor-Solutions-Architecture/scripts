import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"62GUQIFvssTT","alg":"RS256","n":"9NymKGDOArhPvcggSI4kqzhlA8ZtB2IST8kyxDy50IXIuREn","e":"AQAB"}
key_31 = {"kty":"RSA","kid":"62GUQIFvssTT","alg":"RS256","n":"9NymKGDOArhPvcggSI4kqzhlA8ZtB2IST8kyxDy50IXIuREn","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_31, algorithm='RS256').key)
