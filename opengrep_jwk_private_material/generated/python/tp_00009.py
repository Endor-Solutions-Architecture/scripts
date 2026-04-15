import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"c-TrWM-_86Ch","alg":"RS256","n":"73rIuP9KGOtshuEhXRINgM9g5P6tH3HQdF7pHPzRadBDG_B2","e":"AQAB","d":"ZKr5HPzT"}
key_9 = {"kty":"RSA","kid":"c-TrWM-_86Ch","alg":"RS256","n":"73rIuP9KGOtshuEhXRINgM9g5P6tH3HQdF7pHPzRadBDG_B2","e":"AQAB","d":"ZKr5HPzT"}
print(jwt.PyJWK.from_dict(key_9, algorithm='RS256').key)
