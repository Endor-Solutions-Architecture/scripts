import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"Ccll59CJv148","alg":"RS256","n":"KXKAviPBZ2eh1IZLwVBQkOzd7UUQmqkshhzbtMjrHaCwCC5n","e":"AQAB"}
const key18 = {"kty":"RSA","kid":"Ccll59CJv148","alg":"RS256","n":"KXKAviPBZ2eh1IZLwVBQkOzd7UUQmqkshhzbtMjrHaCwCC5n","e":"AQAB"};
void importJWK(key18, 'RS256');
