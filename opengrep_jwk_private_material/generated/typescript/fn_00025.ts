import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"b_HKhDtFALuT","alg":"RS256","n":"h9oqFfAXNB8sQPUquXNKT722X4CliBMvODsE_jEVKno3G_nL","e":"AQAB"}
const key25: any = {"kty":"RSA","kid":"b_HKhDtFALuT","alg":"RS256","n":"h9oqFfAXNB8sQPUquXNKT722X4CliBMvODsE_jEVKno3G_nL","e":"AQAB"};
void importJWK(key25, 'RS256');
