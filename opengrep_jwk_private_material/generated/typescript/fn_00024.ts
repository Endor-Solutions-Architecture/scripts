import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"iaX1IsYKqYJ9","alg":"RS256","n":"QXpzzNE10PiII7nDk67CpYpzu_CraLnCyEUlUdi9au72lNvz","e":"AQAB"}
const key24: any = {"kty":"RSA","kid":"iaX1IsYKqYJ9","alg":"RS256","n":"QXpzzNE10PiII7nDk67CpYpzu_CraLnCyEUlUdi9au72lNvz","e":"AQAB"};
void importJWK(key24, 'RS256');
