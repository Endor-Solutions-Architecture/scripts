import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"JRAA6rpEPlsF","alg":"RS256","n":"ya2eM4RZIlkcS4WCzFZ6kiEOBue5HHpBo4Txd_Xn5Ltg6NQJ","e":"AQAB"}
key_28 = {"kty":"RSA","kid":"JRAA6rpEPlsF","alg":"RS256","n":"ya2eM4RZIlkcS4WCzFZ6kiEOBue5HHpBo4Txd_Xn5Ltg6NQJ","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_28, algorithm='RS256').key)
