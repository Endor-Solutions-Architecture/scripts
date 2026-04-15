import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"V2-pBDmuoTGE","alg":"RS256","n":"ldv8R_0NsG65QQVVmnnJe9PNN46QFwdcW24n7dTFBaxUBYV6","e":"AQAB"}
key_42 = {"kty":"RSA","kid":"V2-pBDmuoTGE","alg":"RS256","n":"ldv8R_0NsG65QQVVmnnJe9PNN46QFwdcW24n7dTFBaxUBYV6","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_42, algorithm='RS256').key)
