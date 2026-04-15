import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"hRVrJJDeMFqx","alg":"RS256","n":"GkFqt9k0i6MrerhijTphQDWQu7VIuoAJQq_o0jOAQQ_annyp","e":"AQAB"}
const key33: any = {"kty":"RSA","kid":"hRVrJJDeMFqx","alg":"RS256","n":"GkFqt9k0i6MrerhijTphQDWQu7VIuoAJQq_o0jOAQQ_annyp","e":"AQAB"};
void importJWK(key33, 'RS256');
