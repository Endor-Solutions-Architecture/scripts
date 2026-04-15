import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"5J4_6b1r2YLZ","alg":"RS256","n":"eoMfK_oKsR38G7lDuZ4_QOsJDnHo1pnFYc4p_EPJchmc_Moo","e":"AQAB"}
const key13 = {"kty":"RSA","kid":"5J4_6b1r2YLZ","alg":"RS256","n":"eoMfK_oKsR38G7lDuZ4_QOsJDnHo1pnFYc4p_EPJchmc_Moo","e":"AQAB"};
void importJWK(key13, 'RS256');
