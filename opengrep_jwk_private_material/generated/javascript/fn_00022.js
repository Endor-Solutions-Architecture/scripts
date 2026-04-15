import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"9FpKAcrWPzpQ","alg":"RS256","n":"RqgOHvQJqGc8NbW4YVTSamdocHM4Yv179KVxeSxRms0sOMVS","e":"AQAB"}
const key22 = {"kty":"RSA","kid":"9FpKAcrWPzpQ","alg":"RS256","n":"RqgOHvQJqGc8NbW4YVTSamdocHM4Yv179KVxeSxRms0sOMVS","e":"AQAB"};
void importJWK(key22, 'RS256');
