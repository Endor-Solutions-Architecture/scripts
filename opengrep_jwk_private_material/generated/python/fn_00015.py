import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"5PH6gXQQOYFa","alg":"RS256","n":"rbLInjpNXKjWbJY3K41_1QCIAOVuF__DPo4CRvTgrnOGjGll","e":"AQAB"}
key_15 = {"kty":"RSA","kid":"5PH6gXQQOYFa","alg":"RS256","n":"rbLInjpNXKjWbJY3K41_1QCIAOVuF__DPo4CRvTgrnOGjGll","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_15, algorithm='RS256').key)
