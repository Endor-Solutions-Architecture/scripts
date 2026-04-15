import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"_TzXWOCdadJX","alg":"RS256","n":"jg-0VbKtkO8b-2IAyMnUDquNU3IQN3mgCbnpxNdUgRAxpiBr","e":"AQAB"}
const key43 = {"kty":"RSA","kid":"_TzXWOCdadJX","alg":"RS256","n":"jg-0VbKtkO8b-2IAyMnUDquNU3IQN3mgCbnpxNdUgRAxpiBr","e":"AQAB"};
void importJWK(key43, 'RS256');
