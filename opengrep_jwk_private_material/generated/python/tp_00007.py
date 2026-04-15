import jwt

# JWK_PAYLOAD: {"kty":"oct","kid":"uCjIm1LMZK2p","alg":"HS256","k":"Koa6N4zqWzcIF9AWFgQYFA_krYSXRCNeUN-LdfU1IwxZYSoAXuYjxU11zNDjlMQ9"}
key_7 = {"kty":"oct","kid":"uCjIm1LMZK2p","alg":"HS256","k":"Koa6N4zqWzcIF9AWFgQYFA_krYSXRCNeUN-LdfU1IwxZYSoAXuYjxU11zNDjlMQ9"}
print(jwt.PyJWK.from_dict(key_7, algorithm='HS256').key)
