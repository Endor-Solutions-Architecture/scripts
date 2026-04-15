import jwt

jwk_private = {
    "kty": "RSA",
    "kid": "example-key-id",
    "alg": "RS256",
    "n": "hyGJ_i8i3GmMrqqqAcBln3Rgc2xC1AtBZTWs5HPZqtgD",
    "e": "AQAB",
    "d": "BH0fuVrVfJ7g9nhi11YNyiMyhQMGoUaScIs86AXVKDCuxBhar15PKf"
}

print(jwt.algorithms.RSAAlgorithm.from_jwk(str(jwk_private)))
