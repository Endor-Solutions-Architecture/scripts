import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key14: any = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key14, 'HS256');
