import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"iPA-rfm5D-R-","alg":"RS256","n":"9yqR_J3p_doKmwQCWApEsV3-t2gLCdCg7-DtjIbw9iFGn7Ek","e":"AQAB"}
const key31: any = {"kty":"RSA","kid":"iPA-rfm5D-R-","alg":"RS256","n":"9yqR_J3p_doKmwQCWApEsV3-t2gLCdCg7-DtjIbw9iFGn7Ek","e":"AQAB"};
void importJWK(key31, 'RS256');
