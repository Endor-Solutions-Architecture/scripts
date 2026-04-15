import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"9kZu9IDer9Xk","alg":"RS256","n":"CKfRYAVfAwH4o5bAYE_Nz5iWB4ZYQPVQ8Xj8AgsfsBY_5Por","e":"AQAB"}
const key39 = {"kty":"RSA","kid":"9kZu9IDer9Xk","alg":"RS256","n":"CKfRYAVfAwH4o5bAYE_Nz5iWB4ZYQPVQ8Xj8AgsfsBY_5Por","e":"AQAB"};
void importJWK(key39, 'RS256');
