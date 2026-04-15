import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key20 = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key20, 'HS256');
