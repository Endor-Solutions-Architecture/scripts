import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"07itZVAFKvQI","alg":"RS256","n":"jGqPb83PgHHJ1C85i1VfP6WrEmS4um8uma3L0emsFWkJ0bh2","e":"AQAB"}
const key46: any = {"kty":"RSA","kid":"07itZVAFKvQI","alg":"RS256","n":"jGqPb83PgHHJ1C85i1VfP6WrEmS4um8uma3L0emsFWkJ0bh2","e":"AQAB"};
void importJWK(key46, 'RS256');
