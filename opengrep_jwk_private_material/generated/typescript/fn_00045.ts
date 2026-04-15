import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"TMBI1MTOppPE","alg":"RS256","n":"qItwlmeEfaZtSoHhcz6tZFlUkUM-GOxqOQ_3VI38GNwem3y9","e":"AQAB"}
const key45: any = {"kty":"RSA","kid":"TMBI1MTOppPE","alg":"RS256","n":"qItwlmeEfaZtSoHhcz6tZFlUkUM-GOxqOQ_3VI38GNwem3y9","e":"AQAB"};
void importJWK(key45, 'RS256');
