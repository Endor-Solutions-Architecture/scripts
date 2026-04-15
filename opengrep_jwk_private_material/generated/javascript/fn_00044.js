import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key44 = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key44, 'HS256');
