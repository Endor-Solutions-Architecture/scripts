import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"DSHSjh3zKH_L","alg":"RS256","n":"HOyBSVqDgKVQNLs8-HiryLRz0iLY0_4aPVzeYCHeGe5qtK2p","e":"AQAB"}
const key21 = {"kty":"RSA","kid":"DSHSjh3zKH_L","alg":"RS256","n":"HOyBSVqDgKVQNLs8-HiryLRz0iLY0_4aPVzeYCHeGe5qtK2p","e":"AQAB"};
void importJWK(key21, 'RS256');
