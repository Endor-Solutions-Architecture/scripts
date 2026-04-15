import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"V01Dblg2UVYB","alg":"RS256","n":"caQDl-2VcVaR0Hr8YMUat94m02_Ka8QTyxs73MoMqLgPDSvk","e":"AQAB"}
key_25 = {"kty":"RSA","kid":"V01Dblg2UVYB","alg":"RS256","n":"caQDl-2VcVaR0Hr8YMUat94m02_Ka8QTyxs73MoMqLgPDSvk","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_25, algorithm='RS256').key)
