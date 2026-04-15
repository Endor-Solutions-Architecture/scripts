import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"gdEJjUQNm3-p","alg":"RS256","n":"vLbJK3js_4wRRi5UXFkfP6HEX3L2xBFNtkK0ioJvMo3kl5VE","e":"AQAB"}
const key15: any = {"kty":"RSA","kid":"gdEJjUQNm3-p","alg":"RS256","n":"vLbJK3js_4wRRi5UXFkfP6HEX3L2xBFNtkK0ioJvMo3kl5VE","e":"AQAB"};
void importJWK(key15, 'RS256');
