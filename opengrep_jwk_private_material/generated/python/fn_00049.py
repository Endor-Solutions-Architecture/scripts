import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"tL4Y_XRlx2eH","alg":"RS256","n":"s2kngnVADBqCv_5-AH7Pt24iEwZxS444Z998pu-HnXQKnzlr","e":"AQAB"}
key_49 = {"kty":"RSA","kid":"tL4Y_XRlx2eH","alg":"RS256","n":"s2kngnVADBqCv_5-AH7Pt24iEwZxS444Z998pu-HnXQKnzlr","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_49, algorithm='RS256').key)
