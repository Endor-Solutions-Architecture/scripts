import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key11 = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key11, 'HS256');
