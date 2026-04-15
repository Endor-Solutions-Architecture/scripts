import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"iAP1xj7A5CAx","alg":"RS256","n":"b-CRY3XPjtd2UyrkkV4o8GWDtxgNQmNGwmYCEbNdVVYqDqBe","e":"AQAB"}
const key37 = {"kty":"RSA","kid":"iAP1xj7A5CAx","alg":"RS256","n":"b-CRY3XPjtd2UyrkkV4o8GWDtxgNQmNGwmYCEbNdVVYqDqBe","e":"AQAB"};
void importJWK(key37, 'RS256');
