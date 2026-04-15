import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"dLlhuSQNRwyU","alg":"RS256","n":"CqDOWN64xmemJ6eatSujRlEhe_zN26KMhrLOf-TNJrT_Hwhj","e":"AQAB"}
const key36: any = {"kty":"RSA","kid":"dLlhuSQNRwyU","alg":"RS256","n":"CqDOWN64xmemJ6eatSujRlEhe_zN26KMhrLOf-TNJrT_Hwhj","e":"AQAB"};
void importJWK(key36, 'RS256');
