import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"HneaIE-ps-1e","alg":"RS256","n":"L9G7g-Xz6RTnXiBsgRDfagDoN4plPln9htP-cl0KOracRCov","e":"AQAB"}
const key10: any = {"kty":"RSA","kid":"HneaIE-ps-1e","alg":"RS256","n":"L9G7g-Xz6RTnXiBsgRDfagDoN4plPln9htP-cl0KOracRCov","e":"AQAB"};
void importJWK(key10, 'RS256');
