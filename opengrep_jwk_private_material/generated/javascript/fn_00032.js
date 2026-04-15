import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key32 = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key32, 'HS256');
