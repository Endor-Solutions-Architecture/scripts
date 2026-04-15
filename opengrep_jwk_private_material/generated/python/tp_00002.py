import jwt

# JWK_PAYLOAD: {"kty":"oct","kid":"j9gTNaSUTFAH","alg":"HS256","k":"etPnZI2wzLZXubHfMlokplFg1prLijEpGR2__rVwC4JYxna-05QywxWJhqQgigNM"}
key_2 = {"kty":"oct","kid":"j9gTNaSUTFAH","alg":"HS256","k":"etPnZI2wzLZXubHfMlokplFg1prLijEpGR2__rVwC4JYxna-05QywxWJhqQgigNM"}
print(jwt.PyJWK.from_dict(key_2, algorithm='HS256').key)
