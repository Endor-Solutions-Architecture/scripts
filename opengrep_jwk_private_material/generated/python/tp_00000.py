import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"uVqxunyauN2z","alg":"RS256","n":"IszznCtP6fVo6hZIFJ0GCZZNkZ5oBq3dFnbXXG_6D-tghIQH","e":"AQAB","d":"VoKY4gGT2sF3kTH7swIathbYR9y2gUcqyY1U8pFDY3noztcn4wwSjexK6ArKj-xR"}
key_0 = {"kty":"RSA","kid":"uVqxunyauN2z","alg":"RS256","n":"IszznCtP6fVo6hZIFJ0GCZZNkZ5oBq3dFnbXXG_6D-tghIQH","e":"AQAB","d":"VoKY4gGT2sF3kTH7swIathbYR9y2gUcqyY1U8pFDY3noztcn4wwSjexK6ArKj-xR"}
print(jwt.PyJWK.from_dict(key_0, algorithm='RS256').key)
