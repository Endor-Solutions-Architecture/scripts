import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"XQs0QPTxs3Cm","alg":"RS256","n":"Lxx6DNHeTdIDHFDoTrfmmrnyrWEyM32zd5JdAXzirg5WIAho","e":"AQAB","p":"4Dkc9yOsGBdh6k4XDo7zEe9X9jmU8ny713ESrNxrNfdvhV4c","q":"qN_nIEObdY30MECRdBt-GZIpQrio6gN4kOFEZjjKQdTVMRui","dp":"JVi0g2D3Yj_nhwPgXoq_6Q3j4QkvGo-JiSnmViwXqespBv5d","dq":"q90dQdtgaSm9zGglpDVoPpGTLa_Yv0VdbfCsX-qOnOkyE6j9"}
key_3 = {"kty":"RSA","kid":"XQs0QPTxs3Cm","alg":"RS256","n":"Lxx6DNHeTdIDHFDoTrfmmrnyrWEyM32zd5JdAXzirg5WIAho","e":"AQAB","p":"4Dkc9yOsGBdh6k4XDo7zEe9X9jmU8ny713ESrNxrNfdvhV4c","q":"qN_nIEObdY30MECRdBt-GZIpQrio6gN4kOFEZjjKQdTVMRui","dp":"JVi0g2D3Yj_nhwPgXoq_6Q3j4QkvGo-JiSnmViwXqespBv5d","dq":"q90dQdtgaSm9zGglpDVoPpGTLa_Yv0VdbfCsX-qOnOkyE6j9"}
print(jwt.PyJWK.from_dict(key_3, algorithm='RS256').key)
