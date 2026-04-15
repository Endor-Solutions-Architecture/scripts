import jwt

jwk_public = {
    "kty": "RSA",
    "kid": "public-only",
    "alg": "RS256",
    "n": "hyGJ_i8i3GmMrqqqAcBln3Rgc2xC1AtBZTWs5HPZqtgD",
    "e": "AQAB"
}

print(jwt.algorithms.RSAAlgorithm.from_jwk(str(jwk_public)))
