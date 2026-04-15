import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"z74B6RtyHqpd","alg":"RS256","n":"WHGm-4cTNsWnU8zmnr2dcCsG6rCed0u0ss4Y1BIuievEsqNF","e":"AQAB"}
const key40: any = {"kty":"RSA","kid":"z74B6RtyHqpd","alg":"RS256","n":"WHGm-4cTNsWnU8zmnr2dcCsG6rCed0u0ss4Y1BIuievEsqNF","e":"AQAB"};
void importJWK(key40, 'RS256');
