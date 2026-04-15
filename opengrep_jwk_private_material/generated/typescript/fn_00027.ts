import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"orGLZR4sDTm1","alg":"RS256","n":"5LQOpMuaGllEuNJVXB7jAJksrOq42Lw5ydrsMNRb-5hxh4-b","e":"AQAB"}
const key27: any = {"kty":"RSA","kid":"orGLZR4sDTm1","alg":"RS256","n":"5LQOpMuaGllEuNJVXB7jAJksrOq42Lw5ydrsMNRb-5hxh4-b","e":"AQAB"};
void importJWK(key27, 'RS256');
