import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"uK_ljWmE96Ss","alg":"RS256","n":"HjCJJdWs5Cl-2fcq0qdYYVF0uG2YHBJSXFu4Y39uGLlJG7Yg","e":"AQAB"}
const key30 = {"kty":"RSA","kid":"uK_ljWmE96Ss","alg":"RS256","n":"HjCJJdWs5Cl-2fcq0qdYYVF0uG2YHBJSXFu4Y39uGLlJG7Yg","e":"AQAB"};
void importJWK(key30, 'RS256');
