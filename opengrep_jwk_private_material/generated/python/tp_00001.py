import jwt

# JWK_PAYLOAD: {"kty":"EC","kid":"EwZ4OfmG-btq","alg":"ES256","crv":"P-256","x":"jNTF_lCTS7K-6CWYUecF47znoD2tNVKBmYUZNKUzfH3","y":"d1q78YJJIRuiwDAfHOyjkTA1m-vEpBHLGv31y8WB_XY","d":"J2YLU1cKcX3C2nNpkG-upDuqbNDHzyEzAF36Kp5bL6uvESSNd0URZhx9rIvbU8iK"}
key_1 = {"kty":"EC","kid":"EwZ4OfmG-btq","alg":"ES256","crv":"P-256","x":"jNTF_lCTS7K-6CWYUecF47znoD2tNVKBmYUZNKUzfH3","y":"d1q78YJJIRuiwDAfHOyjkTA1m-vEpBHLGv31y8WB_XY","d":"J2YLU1cKcX3C2nNpkG-upDuqbNDHzyEzAF36Kp5bL6uvESSNd0URZhx9rIvbU8iK"}
print(jwt.PyJWK.from_dict(key_1, algorithm='ES256').key)
