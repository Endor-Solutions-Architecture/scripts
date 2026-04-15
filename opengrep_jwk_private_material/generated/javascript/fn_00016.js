import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"BCmmXA5rzo0P","alg":"RS256","n":"aRn99aQO9TigiDwCLlVNF_zS-1dimiZITixXpQaxc7m4XrXp","e":"AQAB"}
const key16 = {"kty":"RSA","kid":"BCmmXA5rzo0P","alg":"RS256","n":"aRn99aQO9TigiDwCLlVNF_zS-1dimiZITixXpQaxc7m4XrXp","e":"AQAB"};
void importJWK(key16, 'RS256');
