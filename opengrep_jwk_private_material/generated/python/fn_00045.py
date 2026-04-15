import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"nW3MQ_bolKfY","alg":"RS256","n":"7APEEJLF02KZ5hLgVK_JHHapymNu4c9neD_yi77VLeyyOcou","e":"AQAB"}
key_45 = {"kty":"RSA","kid":"nW3MQ_bolKfY","alg":"RS256","n":"7APEEJLF02KZ5hLgVK_JHHapymNu4c9neD_yi77VLeyyOcou","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_45, algorithm='RS256').key)
