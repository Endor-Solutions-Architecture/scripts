import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"kHKrjIR74DS-","alg":"RS256","n":"YRvdBjWDbJfhE_1E9cMZy8lg7eFTuEElhIqqDC39liWVKW4y","e":"AQAB"}
const key25 = {"kty":"RSA","kid":"kHKrjIR74DS-","alg":"RS256","n":"YRvdBjWDbJfhE_1E9cMZy8lg7eFTuEElhIqqDC39liWVKW4y","e":"AQAB"};
void importJWK(key25, 'RS256');
