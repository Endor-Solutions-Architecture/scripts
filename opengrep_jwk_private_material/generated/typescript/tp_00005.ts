import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"_4KDPxyS1Rql","alg":"RS256","n":"GVZNcmFWEnLK9pi8ThuoiqeTCxoqen1ZMo3fSj6Z1BFqlcwv","e":"AQAB","d":"f8TMWxlcmbgEeOd-jwV30fWj0wU0uROsdHJ5hs7pfu7viUyJpwUIqwSZFFJ7Fus6"}
const key5: any = {"kty":"RSA","kid":"_4KDPxyS1Rql","alg":"RS256","n":"GVZNcmFWEnLK9pi8ThuoiqeTCxoqen1ZMo3fSj6Z1BFqlcwv","e":"AQAB","d":"f8TMWxlcmbgEeOd-jwV30fWj0wU0uROsdHJ5hs7pfu7viUyJpwUIqwSZFFJ7Fus6"};
void importJWK(key5, 'RS256');
