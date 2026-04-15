import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"1mpQMDJxZMLH","alg":"RS256","n":"la_jYMDfQvIM4C_BshqhQVwFJ4UgmUXOlLnVhcv87BelbpPi","e":"AQAB","p":"pACFMtkt5-qtgnTdSJOOtBp-s7ieG3_mGOowxRnFSfyZed7s","q":"T-JwwbFtka2VmjDXBvmFewb4dsAD73onBPcEx3x9oLjp9LVY","dp":"CMPihgt8jGhuB8XPNT36KJxZQtJ1L3jkLb_pjz0cY4xrPJei","dq":"OXxJh-suUTOMR5KUJ6vI8FONz5FeqRJiwgGdNLYYg9zXGDSm"}
key_8 = {"kty":"RSA","kid":"1mpQMDJxZMLH","alg":"RS256","n":"la_jYMDfQvIM4C_BshqhQVwFJ4UgmUXOlLnVhcv87BelbpPi","e":"AQAB","p":"pACFMtkt5-qtgnTdSJOOtBp-s7ieG3_mGOowxRnFSfyZed7s","q":"T-JwwbFtka2VmjDXBvmFewb4dsAD73onBPcEx3x9oLjp9LVY","dp":"CMPihgt8jGhuB8XPNT36KJxZQtJ1L3jkLb_pjz0cY4xrPJei","dq":"OXxJh-suUTOMR5KUJ6vI8FONz5FeqRJiwgGdNLYYg9zXGDSm"}
print(jwt.PyJWK.from_dict(key_8, algorithm='RS256').key)
