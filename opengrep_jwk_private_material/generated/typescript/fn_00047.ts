import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key47: any = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key47, 'HS256');
