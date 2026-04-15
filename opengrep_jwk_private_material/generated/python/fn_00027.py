import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"GTFnxxVliTWS","alg":"RS256","n":"dd_TamP286dxciPA-wrpLouX9je9lc7TLSEeGRI8V22xyaEU","e":"AQAB"}
key_27 = {"kty":"RSA","kid":"GTFnxxVliTWS","alg":"RS256","n":"dd_TamP286dxciPA-wrpLouX9je9lc7TLSEeGRI8V22xyaEU","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_27, algorithm='RS256').key)
