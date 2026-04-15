import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"H_2tn0oHyHj7","alg":"RS256","n":"SaNePr22uCUMXcHqLu8UgazRrd05kfSVwAGFnQTEY2sqaTM5","e":"AQAB"}
const key19 = {"kty":"RSA","kid":"H_2tn0oHyHj7","alg":"RS256","n":"SaNePr22uCUMXcHqLu8UgazRrd05kfSVwAGFnQTEY2sqaTM5","e":"AQAB"};
void importJWK(key19, 'RS256');
