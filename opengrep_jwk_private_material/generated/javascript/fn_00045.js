import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"GTTs1oZFf_6S","alg":"RS256","n":"1lLSVtTWBt3PN5M0cE4fHb4u-FgTfNY0tXPNYMSdI_GPr9el","e":"AQAB"}
const key45 = {"kty":"RSA","kid":"GTTs1oZFf_6S","alg":"RS256","n":"1lLSVtTWBt3PN5M0cE4fHb4u-FgTfNY0tXPNYMSdI_GPr9el","e":"AQAB"};
void importJWK(key45, 'RS256');
