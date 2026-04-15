import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"oSI0IkwyjDoW","alg":"RS256","n":"RJ1oA3GpCdPJYVPuNm63ezMzIslujSkJsraJlCKTzL4UsGXL","e":"AQAB"}
const key36 = {"kty":"RSA","kid":"oSI0IkwyjDoW","alg":"RS256","n":"RJ1oA3GpCdPJYVPuNm63ezMzIslujSkJsraJlCKTzL4UsGXL","e":"AQAB"};
void importJWK(key36, 'RS256');
