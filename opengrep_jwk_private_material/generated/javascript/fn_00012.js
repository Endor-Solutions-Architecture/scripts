import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"ahGlB2cTVgTr","alg":"RS256","n":"vE8fVfC79hER9zFkTgFmNcz5ucRJu7lAbXPpNK-TNdVJbmNp","e":"AQAB"}
const key12 = {"kty":"RSA","kid":"ahGlB2cTVgTr","alg":"RS256","n":"vE8fVfC79hER9zFkTgFmNcz5ucRJu7lAbXPpNK-TNdVJbmNp","e":"AQAB"};
void importJWK(key12, 'RS256');
