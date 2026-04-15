import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"6K0XnchOvQAJ","alg":"RS256","n":"0vUqW_3Uxu0mgUZlr2w9RKM9fniEE4ggf_78zYVbqTwhejuL","e":"AQAB"}
const key33 = {"kty":"RSA","kid":"6K0XnchOvQAJ","alg":"RS256","n":"0vUqW_3Uxu0mgUZlr2w9RKM9fniEE4ggf_78zYVbqTwhejuL","e":"AQAB"};
void importJWK(key33, 'RS256');
