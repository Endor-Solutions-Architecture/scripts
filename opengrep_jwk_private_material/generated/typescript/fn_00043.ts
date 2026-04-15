import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"7YkpVKvMQ3rm","alg":"RS256","n":"NdCXuMCv4hg1iEDrdeXEDUu6TpM8SPGWy4K4qaQS3kTMqHEg","e":"AQAB"}
const key43: any = {"kty":"RSA","kid":"7YkpVKvMQ3rm","alg":"RS256","n":"NdCXuMCv4hg1iEDrdeXEDUu6TpM8SPGWy4K4qaQS3kTMqHEg","e":"AQAB"};
void importJWK(key43, 'RS256');
