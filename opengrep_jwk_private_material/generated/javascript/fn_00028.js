import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"VCwOkLZfcau8","alg":"RS256","n":"LVgtliumKd1VGFazdUu8OsvnYX0Mxbc-Xg0XwvGHlMxS9HNS","e":"AQAB"}
const key28 = {"kty":"RSA","kid":"VCwOkLZfcau8","alg":"RS256","n":"LVgtliumKd1VGFazdUu8OsvnYX0Mxbc-Xg0XwvGHlMxS9HNS","e":"AQAB"};
void importJWK(key28, 'RS256');
