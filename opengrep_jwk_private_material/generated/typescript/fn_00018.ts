import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"OqXkDIkyvmIY","alg":"RS256","n":"4eVVKwBjA5otapp8crk5uBf3HaXLY8f5IsuBwnO5nySUXWnr","e":"AQAB"}
const key18: any = {"kty":"RSA","kid":"OqXkDIkyvmIY","alg":"RS256","n":"4eVVKwBjA5otapp8crk5uBf3HaXLY8f5IsuBwnO5nySUXWnr","e":"AQAB"};
void importJWK(key18, 'RS256');
