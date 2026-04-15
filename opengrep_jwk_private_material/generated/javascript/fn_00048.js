import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"35soi3CT5Vmb","alg":"RS256","n":"XuS5W0RSEUFMjiatgDZ4sx8qZfrsboGgnBO_FwDhJEQdq5Mf","e":"AQAB"}
const key48 = {"kty":"RSA","kid":"35soi3CT5Vmb","alg":"RS256","n":"XuS5W0RSEUFMjiatgDZ4sx8qZfrsboGgnBO_FwDhJEQdq5Mf","e":"AQAB"};
void importJWK(key48, 'RS256');
