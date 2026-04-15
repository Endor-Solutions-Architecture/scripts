import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"c1lBd8xeI522","alg":"RS256","n":"kTrJVZSM63lSKG2XzeXsYKHmZuJ3QeMwaHZE9pqwR324PA_t","e":"AQAB"}
const key10 = {"kty":"RSA","kid":"c1lBd8xeI522","alg":"RS256","n":"kTrJVZSM63lSKG2XzeXsYKHmZuJ3QeMwaHZE9pqwR324PA_t","e":"AQAB"};
void importJWK(key10, 'RS256');
