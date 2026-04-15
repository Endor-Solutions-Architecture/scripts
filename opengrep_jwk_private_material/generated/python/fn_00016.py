import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"wgFJ9PKhqeKq","alg":"RS256","n":"L9QNBkRaolQ5c3mE9k3uahYRHXvHCy2WE1pytvA6j1YOwLQw","e":"AQAB"}
key_16 = {"kty":"RSA","kid":"wgFJ9PKhqeKq","alg":"RS256","n":"L9QNBkRaolQ5c3mE9k3uahYRHXvHCy2WE1pytvA6j1YOwLQw","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_16, algorithm='RS256').key)
