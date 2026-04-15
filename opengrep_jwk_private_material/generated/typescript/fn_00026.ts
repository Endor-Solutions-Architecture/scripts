import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"oct","kid":"missing-k","alg":"HS256"}
const key26: any = {"kty":"oct","kid":"missing-k","alg":"HS256"};
void importJWK(key26, 'HS256');
