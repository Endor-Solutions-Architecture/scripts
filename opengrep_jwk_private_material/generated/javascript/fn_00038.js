import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key38 = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key38, 'HS256');
