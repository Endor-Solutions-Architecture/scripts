import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key41: any = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key41, 'HS256');
