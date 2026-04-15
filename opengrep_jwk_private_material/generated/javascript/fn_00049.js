import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"JJo7Y4VTJhZ4","alg":"RS256","n":"4Jgyw0oYw_8GlPdNYL6pu6bl9600f0XfqUcduo3ZOAPrj73-","e":"AQAB"}
const key49 = {"kty":"RSA","kid":"JJo7Y4VTJhZ4","alg":"RS256","n":"4Jgyw0oYw_8GlPdNYL6pu6bl9600f0XfqUcduo3ZOAPrj73-","e":"AQAB"};
void importJWK(key49, 'RS256');
