import jwt

# JWK_PAYLOAD: {"kty":"RSA","kid":"DS_WwxIC4wqZ","alg":"RS256","n":"Js_O8W8XebK51OG78B_WVvckE3Oz6Ttsh7hV7YO3wjRGv9R4","e":"AQAB"}
key_43 = {"kty":"RSA","kid":"DS_WwxIC4wqZ","alg":"RS256","n":"Js_O8W8XebK51OG78B_WVvckE3Oz6Ttsh7hV7YO3wjRGv9R4","e":"AQAB"}
print(jwt.PyJWK.from_dict(key_43, algorithm='RS256').key)
