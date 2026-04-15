import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"ocyB5HfaMQ_K","alg":"RS256","n":"ukUwf9xcKP9lZH8jqXW3gX05wZDvgp26XMVVyRVyWDdtDUv9","e":"AQAB"}
key_36 = {"kty":"RSA","kid":"ocyB5HfaMQ_K","alg":"RS256","n":"ukUwf9xcKP9lZH8jqXW3gX05wZDvgp26XMVVyRVyWDdtDUv9","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_36, algorithm='RS256').key)
