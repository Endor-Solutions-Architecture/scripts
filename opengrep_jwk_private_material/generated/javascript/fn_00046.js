import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"wQ0YHYANvxLL","alg":"RS256","n":"YMHeqioCKjr7KTVVAJZdFsgjs2kHUVdo0r8kNwDuFPRy-ACu","e":"AQAB"}
const key46 = {"kty":"RSA","kid":"wQ0YHYANvxLL","alg":"RS256","n":"YMHeqioCKjr7KTVVAJZdFsgjs2kHUVdo0r8kNwDuFPRy-ACu","e":"AQAB"};
void importJWK(key46, 'RS256');
