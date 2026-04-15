import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"ujnnkeVOOnBE","alg":"RS256","n":"uQ5SSpKF4Avb-sUgRqaZu-o7zQTg5VXtRchP5QiY-ywuqZRa","e":"AQAB"}
const key40 = {"kty":"RSA","kid":"ujnnkeVOOnBE","alg":"RS256","n":"uQ5SSpKF4Avb-sUgRqaZu-o7zQTg5VXtRchP5QiY-ywuqZRa","e":"AQAB"};
void importJWK(key40, 'RS256');
