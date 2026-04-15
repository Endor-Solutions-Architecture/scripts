import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"D4CnP-0xsbZy","alg":"RS256","n":"yuVJvuZfvkf2DLtlib_7Yoi689Uc4WVWLtadZj6xZz3tjOfG","e":"AQAB"}
const key13: any = {"kty":"RSA","kid":"D4CnP-0xsbZy","alg":"RS256","n":"yuVJvuZfvkf2DLtlib_7Yoi689Uc4WVWLtadZj6xZz3tjOfG","e":"AQAB"};
void importJWK(key13, 'RS256');
