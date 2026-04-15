import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"kfJGbGstIH3d","alg":"RS256","n":"5e7bROqqvwyDmLwRVv3n-gRRkFr8cM8jaJeQNE_1csMNEcM7","e":"AQAB"}
const key19: any = {"kty":"RSA","kid":"kfJGbGstIH3d","alg":"RS256","n":"5e7bROqqvwyDmLwRVv3n-gRRkFr8cM8jaJeQNE_1csMNEcM7","e":"AQAB"};
void importJWK(key19, 'RS256');
