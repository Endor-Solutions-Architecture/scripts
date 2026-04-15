import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"ZRZU9pOUzQbV","alg":"RS256","n":"ZOJRAx0NErQzQBScdWk8cYdy6yvwtjGyVzZqMre6d7iM4Sur","e":"AQAB"}
const key22: any = {"kty":"RSA","kid":"ZRZU9pOUzQbV","alg":"RS256","n":"ZOJRAx0NErQzQBScdWk8cYdy6yvwtjGyVzZqMre6d7iM4Sur","e":"AQAB"};
void importJWK(key22, 'RS256');
