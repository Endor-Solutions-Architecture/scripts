import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"Rh2KwrmHYjm1","alg":"RS256","n":"XPAEGlqKArjBPYNEJSrwZU30rYN5Xb6GUb0tZ9Dl25fPziUF","e":"AQAB"}
const key39: any = {"kty":"RSA","kid":"Rh2KwrmHYjm1","alg":"RS256","n":"XPAEGlqKArjBPYNEJSrwZU30rYN5Xb6GUb0tZ9Dl25fPziUF","e":"AQAB"};
void importJWK(key39, 'RS256');
