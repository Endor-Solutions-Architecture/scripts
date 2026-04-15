import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"ySEcTTPUjv2_","alg":"RS256","n":"66jGYAR7o7Vb-PuWa2C6AK3wokA8NNSv95po6MTzvZ9FV242","e":"AQAB"}
const key48: any = {"kty":"RSA","kid":"ySEcTTPUjv2_","alg":"RS256","n":"66jGYAR7o7Vb-PuWa2C6AK3wokA8NNSv95po6MTzvZ9FV242","e":"AQAB"};
void importJWK(key48, 'RS256');
