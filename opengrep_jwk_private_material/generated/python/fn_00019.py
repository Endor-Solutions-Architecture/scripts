import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"uMQ_IAuJlJdp","alg":"RS256","n":"Ki4IjlXyqqt2BMvo-9q-VPwT8JsyeO6nMwlgfd73j7X3dJb3","e":"AQAB"}
key_19 = {"kty":"RSA","kid":"uMQ_IAuJlJdp","alg":"RS256","n":"Ki4IjlXyqqt2BMvo-9q-VPwT8JsyeO6nMwlgfd73j7X3dJb3","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_19, algorithm='RS256').key)
