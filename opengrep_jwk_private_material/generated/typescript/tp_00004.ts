import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"j6NAkaqk-Gpq","alg":"RS256","n":"2vtssZlltZYGeWgUFGk9Of27DSq43qO9OMuk1t6GzA6oMNt8","e":"AQAB","d":"ttc38a2O"}
const key4: any = {"kty":"RSA","kid":"j6NAkaqk-Gpq","alg":"RS256","n":"2vtssZlltZYGeWgUFGk9Of27DSq43qO9OMuk1t6GzA6oMNt8","e":"AQAB","d":"ttc38a2O"};
void importJWK(key4, 'RS256');
