import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"SsDWdWLFJN9Y","alg":"RS256","n":"0RmeMRNeVUli1UtT5e_PzARynTYK8-Bq5kNxQGczZTZ2V45L","e":"AQAB"}
key_48 = {"kty":"RSA","kid":"SsDWdWLFJN9Y","alg":"RS256","n":"0RmeMRNeVUli1UtT5e_PzARynTYK8-Bq5kNxQGczZTZ2V45L","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_48, algorithm='RS256').key)
