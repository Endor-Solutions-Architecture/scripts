import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"-myPZbsvhfS1","alg":"RS256","n":"BRM34YfjZRfR0vBz5V_TRq_NSTEdjNFId05B7hBtEXWhEAXu","e":"AQAB"}
const key12: any = {"kty":"RSA","kid":"-myPZbsvhfS1","alg":"RS256","n":"BRM34YfjZRfR0vBz5V_TRq_NSTEdjNFId05B7hBtEXWhEAXu","e":"AQAB"};
void importJWK(key12, 'RS256');
