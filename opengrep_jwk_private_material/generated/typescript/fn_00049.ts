import { importJWK } from "jose";
// JWK_PAYLOAD: {"kty":"RSA","kid":"XmNFTWM6VNU5","alg":"RS256","n":"wZQWzh_aob6YEtn5B_onAzCP8Jm5HAytWaFgomFDb5d78j7t","e":"AQAB"}
const key49: any = {"kty":"RSA","kid":"XmNFTWM6VNU5","alg":"RS256","n":"wZQWzh_aob6YEtn5B_onAzCP8Jm5HAytWaFgomFDb5d78j7t","e":"AQAB"};
void importJWK(key49, 'RS256');
