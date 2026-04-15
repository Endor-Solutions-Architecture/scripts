import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"J3V3S40p5bgi","alg":"RS256","n":"SP9HQC8qERPmTeoCyhtgGxS3-9rTdSL31k1AARM6iQIb5UiJ","e":"AQAB"}
const key15 = {"kty":"RSA","kid":"J3V3S40p5bgi","alg":"RS256","n":"SP9HQC8qERPmTeoCyhtgGxS3-9rTdSL31k1AARM6iQIb5UiJ","e":"AQAB"};
void importJWK(key15, 'RS256');
