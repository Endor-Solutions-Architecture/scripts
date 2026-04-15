import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"l8APt2Ac_tiG","alg":"RS256","n":"fimpzwriQD9VuKWV8wI7f06juWcereSVvwxk7YEiI6tqAj5Y","e":"AQAB"}
key_37 = {"kty":"RSA","kid":"l8APt2Ac_tiG","alg":"RS256","n":"fimpzwriQD9VuKWV8wI7f06juWcereSVvwxk7YEiI6tqAj5Y","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_37, algorithm='RS256').key)
