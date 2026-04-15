import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key23: any = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key23, 'HS256');
