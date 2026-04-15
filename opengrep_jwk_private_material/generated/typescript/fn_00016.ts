import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"rd8RjcVkKCAn","alg":"RS256","n":"jkFvf399lBgwLPSdjeFQvtBpsnibsu-q1besZ-gRNyTlU5zO","e":"AQAB"}
const key16: any = {"kty":"RSA","kid":"rd8RjcVkKCAn","alg":"RS256","n":"jkFvf399lBgwLPSdjeFQvtBpsnibsu-q1besZ-gRNyTlU5zO","e":"AQAB"};
void importJWK(key16, 'RS256');
