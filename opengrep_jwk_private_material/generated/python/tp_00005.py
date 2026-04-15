import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"pZJXdpOM0LQU","alg":"RS256","n":"oEZf0bxOfccoume8pLEI04KDOuV560jBAbodrD9RcgKSmS3h","e":"AQAB","d":"0_tDLQcBfwEdUhVfj_bGio98Dz4oMhkJJk5ijFxaYZEOfhhgqWZ4-RKSNM37GzJv"}
key_5 = {"kty":"RSA","kid":"pZJXdpOM0LQU","alg":"RS256","n":"oEZf0bxOfccoume8pLEI04KDOuV560jBAbodrD9RcgKSmS3h","e":"AQAB","d":"0_tDLQcBfwEdUhVfj_bGio98Dz4oMhkJJk5ijFxaYZEOfhhgqWZ4-RKSNM37GzJv"}
print(jwt.PyJWK.from_dict(key_5, algorithm='RS256').key)
